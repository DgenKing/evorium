# Evorium: one-page website (build brief for Codex)

## 0. Read this first

Build a **single-page marketing website** for **Evorium**, an AI-driven game. It must look **seriously
polished**: the kind of page a well-funded indie studio would ship for a launch. It should be **image-heavy and
cinematic**, and it's **plain HTML and CSS** only.

Read `/home/user/projects/evorium/AGENTS.md` and `EVORIUM.md` (§1 The idea, §4 The world, §8 Online plan) to
understand the game. Update EVORIUM.md and README.md when you're done, as AGENTS.md requires.

**Where:** a new folder `/home/user/projects/evorium/website/`. It doesn't touch the game code, the database or
`config.py`.

```
website/
  index.html
  styles.css
  images/          # generated images, optimised WebP plus JPG fallback
  README.md        # how to view it, what each image is and its prompt
```

### Hard rules

- **HTML5 and CSS only.**
  - No frameworks, no build step, no CSS libraries.
  - **At most ~30 lines of plain JavaScript**, for the mobile menu and fade-in-on-scroll. The page must work
    fully with JavaScript off.
  - Google Fonts are allowed (two families at most); everything else is local.
- **No "Home" link in the navigation.** The EVORIUM wordmark links to the top of the page (`#top`).
- **No forms that collect data.** The call to action is "Join the waitlist" linking to `#waitlist`. That
  section says "Coming soon" with a placeholder link, `mailto:` left as `hello@example.com` for the owner to
  change. Don't put any real person's email in the page.
- **All characters are fictional.** Generated people must not resemble real celebrities or public figures. No
  real brand names, logos or trademarks in images (the pub and shop names below are fictional).
- **Accessible:** semantic landmarks, one `h1`, alt text on every image, visible focus styles, contrast at least
  4.5:1 for body text, and `prefers-reduced-motion` turns animations off.
- **Fast:** each image under ~300 KB as WebP (hero under ~450 KB), with `width`/`height` set, `loading="lazy"`
  below the fold, `srcset` with 2 sizes for large images, and `<picture>` with WebP plus JPG fallback.
- **Responsive:** looks designed at 375 px (phone), 768 px and 1440 px+. No horizontal scrolling. Side padding
  at least 16 px on phones.
- **Don't commit.**

---

## 1. Look and feel

**Mood: "Ancoats after dark".**
- Wet Manchester streets, red-brick mills, the warm glow of a pub window.
- Cinematic, moody, grown-up, like a prestige TV drama title sequence crossed with a modern game launch page.
- **Not** sci-fi neon, not cartoon, not generic "AI" circuitry or robot imagery. The AI is invisible; the world
  is the star.

### Colours (use these as CSS custom properties)

| Token | Hex | Use |
|---|---|---|
| `--ink` | `#0D0E11` | page background (near-black, slightly blue) |
| `--ink-2` | `#16181D` | alternate section background, cards |
| `--brick` | `#8E3B2C` | accents, dividers, hover states |
| `--billet` | `#1E3A32` | the pub's dark green; panels and badges |
| `--amber` | `#E8A548` | the signature glow: primary buttons, highlights, key words |
| `--cream` | `#EFE7D6` | headings and body text on dark |
| `--mist` | `#9AA0A8` | secondary text, captions |

- Dark page throughout; amber is the only "loud" colour.
- Use a subtle **film-grain** overlay (CSS: a tiny repeating noise PNG at 4–6 % opacity) and a soft **vignette**
  on hero images.
- Images get a gentle warm-shadow, cool-highlight grade so they all feel like the same film.

### Type

- **Headings:** a refined serif with character, e.g. *Fraunces* or *Playfair Display*, set large with tight
  leading.
- **Body and UI:** a clean grotesque, e.g. *Inter* or *Manrope*.
- **The wordmark "EVORIUM":** spaced capitals (letter-spacing ~0.3em) in the serif, cream, with a faint amber
  glow on hover.
- Body text 18 px (17 px on mobile), line-height 1.6, measure at most 65 characters.

### Motion (subtle)

- Elements fade and rise 16 px into view on scroll (IntersectionObserver adds a class; CSS does the
  animation).
- A slow Ken-Burns zoom on the hero image (CSS only, 30 s, scale 1 → 1.06).
- All of it is disabled under `prefers-reduced-motion`.

---

## 2. The page, section by section

Write all copy in British English, confident and vivid, short sentences, no hype words like "revolutionary"
or "next-gen". The voice is a storyteller, not a tech brochure. **Use the copy below as written** (you may
tighten it, but keep the meaning).

### 2.1 Navigation (sticky, transparent over the hero, solid `--ink` after scrolling)

- Left: the **EVORIUM** wordmark, linking to `#top`.
- Right: **The world** · **The people** · **While you're away** · **How it works** · a small amber button,
  **Join the waitlist**.
- On mobile: the wordmark, plus a menu button that opens a full-screen panel.

### 2.2 Hero (full viewport height) — image `hero.webp`

- Full-bleed hero image with a dark gradient at the bottom for legibility.
- **h1:** "The street doesn't stop when you leave."
- **Subhead:** "Evorium is a living 3D world in Manchester, where every person is run by AI, remembers
  everything, and carries on without you."
- **Buttons:** **Join the waitlist** (amber, solid) · **See how it works** (outline, cream).
- A small line at the bottom: "Ancoats, Manchester · Real time · Always on".

### 2.3 The hook — "A world that lives in real time" — image `rain-window.webp`

Split layout: the image on one side, text on the other.
- **Heading:** "Close the game. The world keeps going."
- **Copy:** "Evorium runs on the real clock. When you log off, the pub still opens at nine. Deals get made.
  Secrets get out. Friendships sour. Come back tomorrow and the street has moved on, and everyone's talking
  about what you did last night."
- Three small stat-style chips below:
  - **24/7**: the world never pauses;
  - **Real time**: a minute here is a minute there;
  - **Every word remembered**: nobody forgets.

### 2.4 The world — "Shuttle Street, Ancoats" — images `street-dusk.webp`, `pub-interior.webp`, `shop-interior.webp`

- **Heading:** "One street. Every story."
- **Copy:** "Red-brick mills, a corner pub that's been pulling pints for a hundred years, and the newsagent two
  doors down. The Crooked Billet and Patel's News are the heart of Shuttle Street, and the heart of a fight for
  its future."
- A **3-image mosaic**: one large (the street at dusk) and two stacked (pub interior, shop interior), each with
  a short caption: "Shuttle Street", "The Crooked Billet", "Patel's News".

### 2.5 The people — eight character cards — images `char-*.webp`

- **Heading:** "They have lives. You're just passing through."
- **Intro:** "Eight neighbours, each with a personality, a past, money worries, secrets and grudges. They talk to
  each other when you're not there. They make plans, keep promises, break them, and remember who was kind and
  who wasn't."
- **Cards:** a 4 × 2 grid on desktop, 2 × 4 on tablet, and a horizontal scroll-snap row on mobile. Each card has
  a portrait (3:4), name, role and a one-line hook. On hover, the portrait lifts and a quote appears.

| File | Name | Role | Hook | Quote on hover |
|---|---|---|---|---|
| `char-dez.webp` | Dez Whitworth | Landlord, The Crooked Billet | His rent's about to nearly double. | "I'm not going to pretend I've got a plan when I haven't." |
| `char-jess.webp` | Jess Hartley | Barmaid, single mum | Needs the hours. Won't take any nonsense. | "You've got a nerve showing your face back in here." |
| `char-raj.webp` | Raj Patel | Newsagent | Sitting on a £45,000 offer he's told no one about. | "What happens to my neighbours matters to me as much as the number." |
| `char-tommy.webp` | Tommy Shaw | Retired bus driver | Knows everyone's business. Lonely since Maureen. | "Forty questions by Sunday, that's a promise." |
| `char-chloe.webp` | Chloe Barlow | Junior architect | Just moved back. Needs a flat she can afford. | "I'm still finding my feet." |
| `char-brenda.webp` | Brenda Ashworth | Tenants' association | Loves a petition and a rota. | "Somebody has to get people organised." |
| `char-mo.webp` | Mo Iqbal | Private hire driver | Hears everything from the back seat. Repeats nothing. | "I just come for the darts." |
| `char-simon.webp` | Simon Ferris | Northgate Estates | Polite, careful, and here to buy the street. | "It's simply where the evidence puts the going rate." |

### 2.6 "While you're away" — a mock catch-up screen — image `catchup-bg.webp`

- **Heading:** "Come back to a different street."
- **Copy:** "Every time you return, Evorium tells you what you missed: who fell out, who signed, who's been
  talking about you."
- **Centrepiece:** an HTML/CSS mock-up (not an image) of an in-game "While you were away" panel. A frosted-glass
  card over the background image, with a small "Previously in Ancoats" label and 4 bullet items that fade in one
  after another:
  - "Raj finally told Dez about Northgate's offer."
  - "Jess barred someone for threatening her. Word's got round."
  - "Dez stayed up going through the books. It doesn't look good."
  - "Tommy says the quiz is back on Thursday."
- Small caption: "Real moments from Evorium's first week."

### 2.7 Your reputation is the game — image `reputation.webp`

- **Heading:** "Be decent. Or don't. They'll remember either way."
- **Copy:** "There are no quest markers telling you who to trust. Help someone and word spreads. Cross someone
  and doors close: the pub bars you, nobody lends you a penny, and the gossip follows you down the street. Your
  standing with the neighbourhood is everything."
- Two contrasting mini-panels side by side:
  - **"Win them over"** (amber edge): "Tips, favours, a seat at the bar, a friend when you need one."
  - **"Cross them"** (brick edge): "Barred, ignored, talked about, on your own."

### 2.8 How it works (plain words, no jargon) — image `how-it-works.webp` (optional)

- **Heading:** "Real people, not scripts."
- **Four steps** in a horizontal row (stacked on mobile), each with a thin-line icon drawn in CSS or inline SVG,
  plus a title and one sentence:
  1. **They think for themselves.** "Every line is written in the moment, in character, by AI."
  2. **They remember what matters.** "Promises, insults, kindness, secrets: kept, scored, never forgotten."
  3. **They make real choices.** "Sign the deal, raise the prices, warn the neighbours. Choices with
     consequences."
  4. **The rules keep it real.** "Money, time and opening hours are enforced by the game, so nobody can magic
     their way out."
- Small note: "Built in Manchester."

### 2.9 Built in 3D — image `unreal-hero.webp`

- **Heading:** "Walk into the pub. Pull up a stool."
- **Copy:** "Evorium is coming to life in Unreal Engine 5: a third-person world you can walk around, where the
  neighbours go about their day and stop to talk to you."
- A wide cinematic image with a thin amber "In development" badge.

### 2.10 Waitlist — `id="waitlist"` — image `waitlist-bg.webp`

- **Heading:** "The street's already awake."
- **Copy:** "Evorium is in development. Be first through the door when it opens."
- Primary amber button **Join the waitlist**, linking to `mailto:hello@example.com?subject=Evorium%20waitlist`
  (a placeholder for the owner to change). Under it, small text: "No spam. Just a knock on the door when we
  open."

### 2.11 Footer

- The **EVORIUM** wordmark (links to `#top`), "© 2026 Evorium", and "Ancoats, Manchester".
- Text links: The world · The people · How it works.
- A tiny line: "All characters are fictional."

---

## 3. Images to generate

Generate every image yourself with your image tool. Keep **one consistent look** across all of them:
- **Cinematic photoreal, 35mm film still, shallow depth of field.**
- **Overcast or dusk Manchester light,** with warm tungsten interiors against a cool blue exterior.
- **Subtle film grain, slightly desaturated.** No text or logos except the fictional signs named below. No
  watermarks, nothing AI-glossy or plastic.

Save the full-size masters as PNG in `website/images/src/`, then export optimised WebP and JPG at the sizes
listed. Record every final prompt in `website/README.md`.

**People:** fictional and ordinary, the kind you'd see in a Manchester pub, not models. Ages and looks follow
the descriptions. Faces natural with real skin texture. For characters with an existing portrait in
`evorium/static/portraits/` (dez, jess, raj, tommy, chloe), **match that person's look** (hair, age, face shape,
build), so the site and the game agree. Open those PNGs and describe them in your prompt.

| File | Size (W×H) | Prompt |
|---|---|---|
| `hero.webp` | 2400×1350 | A cobbled Manchester side street in Ancoats at blue hour after rain. A red-brick Victorian corner pub with a dark green painted frontage and gold sign lettering reading "THE CROOKED BILLET" glows warm amber from its windows. Two doors down, a blue and cream newsagent, "PATEL'S NEWS". Tall red-brick cotton mills and a chimney stack behind, wet setts reflecting the pub light, a lone figure in a coat walking past. Cinematic, moody, 35mm, shallow depth of field, film grain. |
| `rain-window.webp` | 1600×1200 | Inside a traditional Manchester pub at night, looking out through a rain-streaked sash window at a wet red-brick street. A half-finished pint of bitter on the sill, warm lamp light inside, cool blue street light outside. Intimate, quiet, cinematic. |
| `street-dusk.webp` | 1800×1200 | Wide shot of a short terrace street in Ancoats at dusk: the dark green Crooked Billet pub and the blue and cream Patel's News side by side, an empty unit between them with a faded "TO LET" board, iron bollards, a bicycle locked to a rail, mill buildings behind. Cinematic, desaturated, film grain. |
| `pub-interior.webp` | 1200×900 | Interior of an old Manchester free house: dark oak bar, brass hand pumps, oxblood leather booths, a dartboard on the back wall, warm low light, a few regulars in soft focus, a barmaid in her thirties with tied-back dark hair pulling a pint. Cinematic, natural, film still. |
| `shop-interior.webp` | 1200×900 | Interior of a small family-run Manchester newsagent early morning: a newspaper rack, a counter with a till, drinks chillers glowing at the back, a parcel shelf. A man in his early forties with neat dark hair behind the counter, thoughtful. Natural light, film still. |
| `char-dez.webp` | 900×1200 | Portrait of Dez, 54, a Manchester pub landlord: greying short hair, weathered kind face, stubble, dark polo shirt, standing behind his bar, warm pub light, a tired half-smile. Match `portraits/dez.png`. |
| `char-jess.webp` | 900×1200 | Portrait of Jess, 34, a barmaid and single mum: sharp, funny, tired eyes, dark hair tied back, black top, behind a pub bar. Match `portraits/jess.png`. |
| `char-raj.webp` | 900×1200 | Portrait of Raj, 41, a careful, shrewd newsagent: neat dark hair, short beard, cardigan over a shirt, behind his shop counter. Match `portraits/raj.png`. |
| `char-tommy.webp` | 900×1200 | Portrait of Tommy, 67, a retired bus driver and lifelong regular: balding white hair, warm crinkled smile, navy jumper over a checked shirt, at his usual pub table. Match `portraits/tommy.png`. |
| `char-chloe.webp` | 900×1200 | Portrait of Chloe, 29, a junior architect just back in Manchester: friendly, optimistic, light-brown hair, green jacket, outside on a red-brick street. Match `portraits/chloe.png`. |
| `char-brenda.webp` | 900×1200 | Portrait of Brenda, 71, a brisk, kind retired school dinner lady who chairs a tenants' association: short curly grey hair, lilac cardigan, holding a clipboard, outside a housing block. |
| `char-mo.webp` | 900×1200 | Portrait of Mo, 38, an easygoing, observant private hire driver: short dark hair, trimmed beard, dark jacket, leaning on the open door of a car on a Manchester street at night. |
| `char-simon.webp` | 900×1200 | Portrait of Simon, 46, a polite, corporate asset manager at a property company: neat dark hair, charcoal suit, no tie, standing outside a red-brick terrace holding a slim folder, composed and unreadable. |
| `catchup-bg.webp` | 2000×1200 | Moody blurred view down Shuttle Street at night: wet setts, the pub's warm windows, street lamps, bokeh. Designed as a background for overlaid text (keep the centre calm). |
| `reputation.webp` | 1600×1000 | Inside the pub: a barmaid with folded arms facing a man at the door, regulars watching from their booths in soft focus. Tense but not violent. Cinematic. |
| `how-it-works.webp` | 1600×900 | Optional. A long-exposure night shot of Ancoats with light trails, suggesting time passing; or a pub clock above the bar showing nearly midnight. |
| `unreal-hero.webp` | 2400×1000 | A stylised but realistic real-time 3D game render (Unreal Engine look): a third-person view over the shoulder of a player character standing on the pavement outside the green Crooked Billet pub, with the blue and cream newsagent next door, red-brick mills behind, overcast daylight. Clean, believable, game-like. |
| `waitlist-bg.webp` | 2000×1000 | The Crooked Billet's front door slightly ajar at night, warm light spilling onto wet steps. Inviting. |
| `og-image.jpg` | 1200×630 | A social share card: the hero street scene with "EVORIUM" in spaced cream serif capitals and the line "The street doesn't stop when you leave." |
| `grain.png` | 200×200 | A seamless monochrome film-grain noise tile, transparent PNG. |

If image generation isn't available to you, stop after building the page with tasteful CSS placeholders
(gradient blocks in the palette, with the filename and prompt in a comment), and list exactly which images are
missing.

---

## 4. Details that make it feel premium

- **Generous spacing:** sections at least 120 px tall on desktop and 80 px on mobile, with a consistent 8 px
  spacing scale.
- **Large type:** h1 around `clamp(2.6rem, 6vw, 5.5rem)`, h2 around `clamp(2rem, 4vw, 3.4rem)`.
- **Small uppercase eyebrow labels** above headings, in amber with letter-spacing ("THE WORLD", "THE PEOPLE"…).
- **Thin 1 px dividers** in `--brick` at 40 % opacity, plus one hairline amber underline under section
  headings.
- **Buttons:** 14 px radius, 14 × 26 px padding, a soft amber glow on hover, and a visible focus ring.
- **Images:** 12 px radius on cards and mosaics. Full-bleed images have no radius.
- **Head tags:** a favicon (an "E" monogram in amber on ink, as inline SVG), Open Graph and Twitter meta tags
  using `og-image.jpg`, a meta description, `theme-color` `#0D0E11`, and a page title like "Evorium — The
  street doesn't stop when you leave".
- **Smooth scrolling** to anchors, with sticky-header offset handled by `scroll-margin-top`.
- **Print:** none needed.

---

## 5. When you're done

1. Open `index.html` locally and check it at 375, 768 and 1440 px widths (headless browser screenshots if you
   have one; save them to `website/screenshots/`).
2. Check the validity of the HTML and CSS, all images load, alt text everywhere, and no horizontal scroll on
   mobile. Check the total page weight (aim for under 5 MB with all images, and under 1.5 MB for the first
   screen).
3. Write `website/README.md`: how to view it (just open `index.html`, or
   `python3 -m http.server -d website 8080`), the colour tokens, fonts, every image with its final prompt, and
   what the owner should change (the waitlist email).
4. Add a dated line to EVORIUM.md §5 (and §10 Art), as AGENTS.md requires.
5. Final message: files created, screenshots taken, anything not generated or not checked. Don't commit.
