"""Typed promises: only durable, attributed game events can establish completion."""
import json
from datetime import datetime, timedelta
from evorium import places, world

FMT = '%Y-%m-%d %H:%M'
KINDS = {'action', 'visit', 'talk', 'tell', 'make', 'pay', 'conditional', 'vague'}


def _person(c, name, owner):
    if not isinstance(name, str):
        raise ValueError('A person must be named.')
    rows = c.execute("SELECT * FROM agents WHERE kind IN ('npc','player') AND (lower(name)=lower(?) OR lower(substr(name,1,instr(name||' ',' ')-1))=lower(?))",
                     (name, name)).fetchall()
    if len(rows) != 1 or rows[0]['id'] == owner['id']:
        raise ValueError('Choose another established character by full name.')
    return dict(rows[0])


def validate_target(c, owner, kind, target, nested=False):
    """Invalid/unsupported targets become vague. Never infer a target from prose."""
    from evorium import actions
    try:
        if kind not in KINDS or not isinstance(target, dict):
            raise ValueError('Unknown promise type.')
        t = dict(target)
        if kind == 'action':
            if set(t) != {'key', 'args'}:
                raise ValueError('Action needs key and args.')
            item = actions.REGISTRY[t['key']]
            if item.who not in ('any', owner['name'].split()[0]) or owner['kind'] != 'npc':
                raise ValueError('Not this character’s action.')
            t['args'] = item.args_schema.model_validate(t['args']).model_dump()
            if item.key in ('tell', 'ask_loan'):
                other = _person(c, t['args']['person'], owner)
                t['args']['person'] = other['name']
            if item.key == 'tell' and not c.execute('SELECT 1 FROM facts WHERE id=? AND agent_id=?',
                                                   (t['args']['fact_id'], owner['id'])).fetchone():
                raise ValueError('Unknown information.')
        elif kind == 'visit':
            if set(t) - {'place', 'start_at', 'end_at'} or t.get('place') not in places.REGISTRY:
                raise ValueError('Unknown place.')
            for key in ('start_at', 'end_at'):
                if key in t:
                    datetime.strptime(t[key], FMT)
            if t.get('start_at') and t.get('end_at') and t['start_at'] >= t['end_at']:
                raise ValueError('Empty visit window.')
        elif kind in ('talk', 'tell'):
            allowed = {'person'} if kind == 'talk' else {'person', 'fact_id'}
            if set(t) != allowed:
                raise ValueError('Name the person and, for tell, a known fact id.')
            t['person'] = _person(c, t['person'], owner)['name']
            if kind == 'tell' and (type(t['fact_id']) is not int or not c.execute(
                    'SELECT 1 FROM facts WHERE id=? AND agent_id=?', (t['fact_id'], owner['id'])).fetchone()):
                raise ValueError('Unknown information.')
        elif kind == 'make':
            if set(t) != {'item', 'count'} or t['item'] != 'quiz_questions' or owner['name'].split()[0] != 'Tommy':
                raise ValueError('Only Tommy can write quiz questions with the current menu.')
            if type(t['count']) is not int or not 1 <= t['count'] <= 60:
                raise ValueError('Invalid question count.')
        elif kind == 'pay':
            if any(type(value) is not int or value < 1 for value in t.values()):
                raise ValueError('Settlement ids must be positive integers.')
            if set(t) == {'ask_id'}:
                row = c.execute("SELECT * FROM asks WHERE id=? AND kind='ask_loan' AND to_id=?", (t['ask_id'], owner['id'])).fetchone()
            elif set(t) == {'offer_id'}:
                row = c.execute("SELECT * FROM offers WHERE id=? AND kind IN ('loan','surrender','renewal','job') AND (from_id=? OR to_id=?)",
                                (t['offer_id'], owner['id'], owner['id'])).fetchone()
            else:
                row = None
            if not row:
                raise ValueError('No matching ledger settlement.')
        elif kind == 'conditional':
            if nested or set(t) != {'condition', 'trigger', 'promise'} or not isinstance(t['condition'], str) or not t['condition'].strip():
                raise ValueError('Conditional needs a concrete trigger and inner promise.')
            trigger = t['trigger']; inner = t['promise']
            if set(trigger) != {'person', 'kind', 'target'} or set(inner) != {'kind', 'target'}:
                raise ValueError('Unknown conditional shape.')
            who = c.execute("SELECT * FROM agents WHERE name=? AND kind IN ('npc','player')", (trigger['person'],)).fetchone()
            if not who:
                raise ValueError('Unknown trigger actor.')
            tk, tt = validate_target(c, dict(who), trigger['kind'], trigger['target'], True)
            ik, it = validate_target(c, owner, inner['kind'], inner['target'], True)
            if tk in ('vague', 'conditional') or ik in ('vague', 'conditional'):
                raise ValueError('Uncheckable condition or consequence.')
            t = {'condition': t['condition'], 'trigger': {'person': who['name'], 'kind': tk, 'target': tt},
                 'promise': {'kind': ik, 'target': it}}
        else:
            return 'vague', {}
        return kind, t
    except (ValueError, TypeError, KeyError, AttributeError):
        return 'vague', {}


def made_at(c, p):
    if p.get('made_at'):
        return p['made_at']
    row = c.execute('SELECT sim_at FROM conversations WHERE id=?', (p.get('source_conversation_id'),)).fetchone()
    return row['sim_at'] if row else None


def _target(p):
    try:
        value = json.loads(p.get('target_json') or '{}')
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _actions(c, owner, start, end, key=None):
    return [dict(r) for r in c.execute("""SELECT * FROM actions WHERE agent_id=? AND status='done'
        AND sim_at>=? AND (? IS NULL OR sim_at<=?) AND (? IS NULL OR key=?) ORDER BY sim_at,id""",
        (owner, start, end, end, key, key))]


def quiz_progress(c, p):
    start = made_at(c, p)
    if not start:
        return 0, []
    rows = [dict(r) for r in c.execute("""SELECT s.*,a.agent_id FROM stat_changes s JOIN actions a ON a.id=s.action_id
        WHERE a.agent_id=? AND a.key='write_quiz_questions' AND a.status='done'
        AND s.key='pub.quiz_questions_ready' AND a.sim_at>=? AND s.sim_at>=?
        AND (? IS NULL OR s.sim_at<=?) AND (? IS NULL OR a.sim_at<=?) ORDER BY s.sim_at,s.id""",
        (p['agent_id'], start, start, p.get('evidence_until'), p.get('evidence_until'),
         p.get('evidence_until'), p.get('evidence_until')))]
    return sum(max(0, r['new'] - r['old']) for r in rows), rows


def condition_evidence(c, p):
    t = _target(p)
    trigger = t.get('trigger', {})
    who = c.execute('SELECT id FROM agents WHERE name=?', (trigger.get('person'),)).fetchone()
    if not who:
        return None
    return evidence_for(c, {**p, 'agent_id': who['id'], 'kind': trigger.get('kind'),
                            'target_json': json.dumps(trigger.get('target', {}))})


def effective_promise(c, p):
    """Conditional consequences start only once their trigger is demonstrable."""
    p = dict(p)
    if p.get('kind') != 'conditional':
        return p
    rows = condition_evidence(c, p)
    if not rows:
        return None
    inner = _target(p)['promise']
    at = min(r['sim_at'] for r in rows)
    return {**p, 'kind': inner['kind'], 'target_json': json.dumps(inner['target']), 'made_at': at}


def evidence_for(c, commitment):
    """Return supporting rows, or None. Real-time created_at is never used as game time."""
    p = dict(commitment)
    owner = c.execute('SELECT * FROM agents WHERE id=?', (p['agent_id'],)).fetchone()
    if not owner:
        return None
    kind, t = validate_target(c, dict(owner), p.get('kind'), _target(p))
    start = made_at(c, p); end = p.get('evidence_until')
    if not start or kind == 'vague':
        return None
    if kind == 'conditional':
        inner = effective_promise(c, p)
        return evidence_for(c, inner) if inner else None
    aid = p['agent_id']
    if kind == 'action':
        rows = []
        for r in _actions(c, aid, start, end, t['key']):
            rk, rt = validate_target(c, dict(owner), 'action', {'key': r['key'], 'args': json.loads(r['args_json'])})
            if rk == 'action' and rt == t:
                rows.append(r)
    elif kind == 'visit':
        start = max(start, t.get('start_at', start))
        upper = min(x for x in (end, t.get('end_at')) if x) if end or t.get('end_at') else None
        rows = [dict(r) for r in c.execute("""SELECT * FROM timeline WHERE agent_id=? AND kind='arrival'
            AND sim_at>=? AND (? IS NULL OR sim_at<=?) ORDER BY sim_at,id""", (aid, start, upper, upper))
                if r['text'].endswith('(' + places.REGISTRY[t['place']] + ')')]
        rows += [dict(r) | {'sim_at': r['end_at']} for r in c.execute("""SELECT * FROM plans WHERE agent_id=? AND action='visit'
            AND status='done' AND place=? AND start_at>=? AND (? IS NULL OR end_at<=?) ORDER BY end_at,id""",
            (aid, t['place'], start, upper, upper))]
    elif kind == 'talk':
        other = _person(c, t['person'], dict(owner))['id']
        rows = [dict(r) for r in c.execute("""SELECT v.* FROM conversations v WHERE v.status='completed'
            AND ((v.agent_a_id=? AND v.agent_b_id=?) OR (v.agent_a_id=? AND v.agent_b_id=?))
            AND v.sim_at>=? AND (? IS NULL OR v.sim_at<=?) AND v.id!=coalesce(?,0)
            AND EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id=v.id AND m.speaker_id=?) ORDER BY v.sim_at,v.id""",
            (aid, other, other, aid, start, end, end, p.get('source_conversation_id'), aid))]
    elif kind == 'tell':
        other = _person(c, t['person'], dict(owner))['id']
        fact = c.execute('SELECT content FROM facts WHERE id=? AND agent_id=?', (t['fact_id'], aid)).fetchone()
        rows = []
        for r in _actions(c, aid, start, end, 'tell'):
            rk, rt = validate_target(c, dict(owner), 'action', {'key': 'tell', 'args': json.loads(r['args_json'])})
            if rk == 'action' and rt['args'] == {'person': t['person'], 'fact_id': t['fact_id']}:
                rows.append(r)
        rows += [dict(r) for r in c.execute("""SELECT f.*,v.sim_at FROM facts f JOIN conversations v ON v.id=f.source_conversation_id
            WHERE f.agent_id=? AND f.source='told' AND f.source_agent_id=? AND f.content=?
            AND v.status='completed' AND ((v.agent_a_id=? AND v.agent_b_id=?) OR (v.agent_a_id=? AND v.agent_b_id=?))
            AND v.sim_at>=? AND (? IS NULL OR v.sim_at<=?) AND v.id!=coalesce(?,0)
            AND EXISTS(SELECT 1 FROM messages m WHERE m.conversation_id=v.id AND m.speaker_id=?) ORDER BY v.sim_at,f.id""",
            (other, aid, fact['content'], aid, other, other, aid, start, end, end, p.get('source_conversation_id'), aid))]
    elif kind == 'make':
        count, rows = quiz_progress(c, p)
        if count < t['count']:
            return None
    elif kind == 'pay':
        rows = []
        if 'ask_id' in t:
            q = c.execute("SELECT * FROM asks WHERE id=? AND status IN ('accepted','paid') AND to_id=?", (t['ask_id'], aid)).fetchone()
            if q:
                rows = [r for r in _actions(c, aid, start, end, 'answer_ask') if json.loads(r['args_json']) == {'ask_id': q['id'], 'answer': 'yes'}]
        else:
            o = c.execute("SELECT * FROM offers WHERE id=? AND status='accepted' AND resolved_at>=? AND (? IS NULL OR resolved_at<=?)",
                          (t['offer_id'], start, end, end)).fetchone()
            if o:
                for r in _actions(c, aid, start, end):
                    args = json.loads(r['args_json'])
                    direct = o['to_id'] == aid and r['key'] == 'accept_' + o['kind'] and args == {'offer_id': o['id']}
                    loan = o['kind'] == 'loan' and o['from_id'] == aid and o['source_action_id'] == r['id'] and r['key'] == 'answer_ask' and args.get('answer') == 'yes'
                    if direct or loan:
                        rows.append(r)
    else:
        rows = []
    return rows or None


def progress(c, commitment):
    p = dict(commitment)
    if p.get('kind') == 'conditional':
        inner = effective_promise(c, p)
        return progress(c, inner) if inner else 'Condition not yet established by world records.'
    if p.get('kind') == 'make':
        count, _ = quiz_progress(c, p)
        return f"You have written {count} of {_target(p).get('count', '?')} quiz questions."
    return 'Database evidence recorded.' if evidence_for(c, p) else 'No matching database evidence yet.'


def had_chance(c, commitment, until):
    """Accumulate a full hour of awake/free opportunity in half-hour routine samples."""
    p = dict(commitment)
    start = made_at(c, p)
    if not start:
        return False
    actor = c.execute('SELECT * FROM agents WHERE id=?', (p['agent_id'],)).fetchone()
    from evorium.economy import stats
    values = stats(c); t = _target(p)
    cursor = datetime.strptime(start, FMT); stop = datetime.strptime(until, FMT)
    if p.get('kind') == 'visit':
        if t.get('start_at'):
            cursor = max(cursor, datetime.strptime(t['start_at'], FMT))
        if t.get('end_at'):
            stop = min(stop, datetime.strptime(t['end_at'], FMT))
    seconds = 0
    while cursor < stop:
        following = min(stop, cursor + timedelta(minutes=30))
        free = world.is_free(actor['name'], cursor, values) and world.routine(actor['name'], cursor, values)[1] != 'asleep'
        if free and p.get('kind') == 'visit':
            free = places.is_open(t['place'], cursor, values)
        if free and p.get('kind') in ('talk', 'tell'):
            free = world.routine(t['person'], cursor, values)[1] != 'asleep'
        if free:
            seconds += (following - cursor).total_seconds()
            if seconds >= 3600:
                return True
        cursor = following
    return False



def plan_supports(c, plan, commitment, now, conversation_id=None):
    p = effective_promise(c, dict(commitment) | {'evidence_until': now.strftime(FMT)})
    if not p or plan['agent_id'] != p['agent_id']:
        return False
    rows = evidence_for(c, p) or []
    if p.get('kind') == 'visit' and plan['action'] == 'visit':
        return any(r.get('action') == 'visit' and r['id'] == plan['id'] for r in rows)
    if p.get('kind') == 'talk' and plan['action'] == 'phone' and conversation_id:
        return any(r.get('agent_a_id') is not None and r['id'] == conversation_id for r in rows)
    if p.get('kind') == 'tell' and plan['action'] == 'phone' and conversation_id:
        return any(r.get('source_conversation_id') == conversation_id for r in rows)
    return False
