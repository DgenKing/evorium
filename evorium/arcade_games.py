"""Arcade catalogue, restricted game hosting, and personal scores."""
import json
from pathlib import Path
import re

from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from evorium import accounts
from evorium.arcade import NORMAN
from evorium.db import connect

GAMES_DIR = Path(__file__).parent / 'static' / 'games'
GAMES = {}
for entry in json.loads((GAMES_DIR / 'games.json').read_text(encoding='utf-8')):
    slug = entry['slug']
    if slug in GAMES or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
        raise ValueError(f'Invalid arcade game slug: {slug}')
    GAMES[slug] = entry

GAME_POLICY = (
    "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline' blob:; "
    "style-src 'unsafe-inline'; img-src data: blob:; media-src data: blob:; "
    "connect-src 'none'; worker-src 'none'; frame-src 'none'; form-action 'none'; "
    "base-uri 'none'; frame-ancestors 'self'"
)


def _bridge(slug):
    return f"""<script>
window.evoriumGameScore = score => {{
  if (window.parent !== window)
    parent.postMessage({{type:'evorium:score', slug:{json.dumps(slug)}, score}}, '*');
}};
window.addEventListener('keydown', event => {{
  if (event.key !== 'Escape' || window.parent === window) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  parent.postMessage({{type:'evorium:exit'}}, '*');
}}, {{capture:true}});
</script>
""".encode()


class GameFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        slug = path.removesuffix('/index.html')
        if slug in GAMES and path == f'{slug}/index.html' and response.status_code == 200:
            from starlette.concurrency import run_in_threadpool
            source = await run_in_threadpool((GAMES_DIR / slug / 'index.html').read_bytes)
            script = re.search(rb'<script\b|</head\s*>', source, flags=re.I)
            at = script.start() if script else len(source)
            response = HTMLResponse(source[:at] + _bridge(slug) + source[at:])
        response.headers['Content-Security-Policy'] = GAME_POLICY
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-DNS-Prefetch-Control'] = 'off'
        return response


def scores(db_path):
    with connect(db_path) as c:
        return dict(c.execute('SELECT slug, score FROM arcade_scores WHERE account=?',
                              (accounts.current.get(),)))


def save_score(db_path, slug, score):
    if slug not in GAMES:
        raise KeyError(slug)
    game = GAMES[slug]
    spec = game.get('score', {})
    if type(score) is not int or not spec.get('min', 0) <= score <= spec.get('max', 2147483647):
        raise ValueError('Invalid score for this game.')
    account = accounts.current.get()
    with connect(db_path) as c:
        c.execute('BEGIN IMMEDIATE')
        previous = c.execute('SELECT score,fact_id FROM arcade_scores WHERE account=? AND slug=?',
                             (account, slug)).fetchone()
        if previous:
            improved = score < previous['score'] if spec.get('lower') else score > previous['score']
            if not improved:
                return {'best': previous['score'], 'improved': False}

        norman = c.execute("SELECT id FROM agents WHERE name=? AND kind='npc'", (NORMAN,)).fetchone()
        fact_id = previous['fact_id'] if previous else None
        if norman:
            name = accounts.player_row(c)['name']
            unit = spec.get('unit', 'points')
            value = f'{unit} {score}' if unit in ('wave', 'arena') else f'{score} {unit}'
            content = f"In my Gun Street Amusements notebook, {name}'s personal best at {game['title']} is {value}."
            if fact_id:
                c.execute("UPDATE facts SET content=? WHERE id=? AND agent_id=?",
                          (content, fact_id, norman['id']))
            else:
                fact_id = c.execute("""INSERT INTO facts(agent_id,subject,content,source,importance)
                    VALUES (?,'arcade notebook',?,'observed',3)""", (norman['id'], content)).lastrowid
        c.execute("""INSERT INTO arcade_scores(account, slug, score, fact_id) VALUES (?,?,?,?)
            ON CONFLICT(account,slug) DO UPDATE SET score=excluded.score,fact_id=excluded.fact_id""",
                  (account, slug, score, fact_id))
    return {'best': score, 'improved': True}
