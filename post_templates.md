# Post template library

The Canva post styles the engine knows how to fill, one recipe each. A template is a look, not a message: the words always come from the student's own plan, swapped for their treatment, and the photos come from their own clips (or the pictures they send). The template's example words and photos are always thrown away.

Every recipe follows the house rules:

- **Sizes:** posts are 1080 x 1350. Export PNG at 1080 x 1350.
- **Centred:** each slide's words (and card or pictures) sit in the middle of the slide, up and down and side to side. Work out the height of the whole block, then place it in the middle. Slides of the same kind match exactly: the heading sits on the same line every time, so nothing jumps when you swipe.
- **Readable:** line spacing at least 0.92 on headings and 0.95 on body text, so lines never touch.
- **No word on its own line** (Frances, 2026-11-02): a sentence fits on one line, or its lines are about even. Fix it with a line break that balances the lines, or the words a touch smaller so it fits on one line. Sizes stay the same on every slide of a carousel and every quote post, so a size change goes on the whole set.
- **Never words over a face** (Frances, 2026-11-02): every photo behind words is cropped by `engine/post_photos.py` so faces sit above or below the words (`--zone top` for designs with their words at the top), and checked by eye.
- **Handle:** their Instagram handle replaces the template's in the bottom-left corner of every slide.
- **Tidy:** take off template decorations that sit in different places on each slide (little pills, smudges, outlines).
- **Photos behind words:** 40 to 55% see-through over the template's dark background, so white words read clearly.

The Canva design IDs below are Frances's own, for reference only. A student's copy of each template comes from the link in their plan ("Use template").

**This library grows every month.** Each new monthly plan can bring new post styles. When a plan uses a Canva template that isn't here yet, Frances makes it once on her own clinic, gets the look right, and a new recipe is added below (what it's for, her reference design, the layout numbers, the picture briefs, and any rules learnt along the way). New recipes reach students with the next engine update, so the subscription brings new styles as well as new plans.

**Adding a style to the post library page** (what students browse): add an entry to `engine/post_library.json` (name, tab, number of slides, what it's for, what they'll need, search words, the recipe number and the example pictures), then run `python3 engine/make_library.py`. The page is saved as `My Content/library/index.html`. Example pictures are "Your Clinic" samples made with Frances's own Dropbox photos and made-up sample reviews, saved in `My Content/library-samples/<style id>/` (off GitHub). After running it, republish `My Content/library/share.html` to keep the shared link up to date.

---

## 1. Quote post (single image)

**Used for:** quote posts ("Growth Post, Static Quote").
**Frances's reference:** "Copy of TEMPLATE: Static quotes" (DAHXgdbeQjc). Finished examples: Skin Survival 5th, 16th and 29th October.

- **Frances's rule for every quote design (2026-11-09): a plain background with dark words.** One flat colour behind the quote, never a photo, pattern, texture or picture; if a quote template comes with one, swap it for the plain colour. This goes for any quote design added later too.
- Background: a full-page rectangle in the **lightest** colour from their brand, sent to the back.
- Words: their **darkest** brand colour, checked for readability on the background (not dark enough to read easily: charcoal #2D2E30).
- The quote always starts on the same line with the same left edge: text pinned from the top (top 540, left 206).
- The quote in normal sentence letters, even if the plan writes it in CAPITALS. The words themselves never change; proper nouns keep their capitals.
- No brand yet? Use Frances's palette: beige #E0D8D0 background, charcoal #2D2E30 words.

## 2. Client review carousel (10 slides)

**Used for:** client review carousels.
**Frances's reference:** "GROWTH COACH - REVIEW CAROUSEL". Finished example: "Skin Survival: 21st October review carousel" (DAHXgqb7h6I).

Slides: 1 cover review, 2 "We're <clinic>" intro, 3 to 6 one review each with a short story underneath, 7 "If you are…" problems, 8 "Why <clinic>?" reasons, 9 "At <clinic>" benefit line, 10 the plan's call to action.

- **Review cards** look like real Google reviews. Make them with `python3 engine/review_card.py "<reviews.md>" "<Name>" ... --out <folder>`: initial in a coloured circle, name, the Google "G", gold stars, their exact words, "Posted on Google", one text size for the whole set. Cards are 1220 x 1128 and fill a 610.5 x 564.4 frame (left 235).
- **Heading:** "CLIENT REVIEW:" (not "CLIENT RESULT:", because these reviews are about the experience, not results).
- **Review slides 3 to 6:** heading top 240, card top 350, story top 960. Text boxes left 140, 800 wide. Headings 60, body 38, line spacing 1.15.
- **Other slides:** the same sizes and gap (110 from the top of the heading to the top of the words), with the block centred on the slide.
- **Stories under reviews:** one or two warm sentences retelling the experience in the clinic's words. Never add results or claims the review doesn't make.
- **Review rules:** 5-star only, the client's exact words, never changed; leave out any review with a results claim (hair reduction, pain-free, number of sessions, "haven't shaved since"); first name and initial.
- Backgrounds: their clinic photos at 40%.

## 3. Words-on-photos carousel (library: "Bold words on photos" and "Same heading, one point a slide") (any number of slides)

**Used for:** carousels where each slide is words over a photo (myth-busting, "In for October" lists, story carousels).
**Frances's reference:** "SKIN SURVIVAL- PIGMENTATION" (DAHXg8fOd3o). Finished examples: "Skin Survival: 7th October carousel" (DAHXg6PymE0, 10 slides) and "Skin Survival: 14th October carousel" (DAHXgx-PNGI, 5 slides). This is also the fallback when a plan's template link won't copy.

- Each slide: a full-page photo from their clips at 55% over charcoal, a bold heading (64, line spacing 0.92) and normal body text (46 for longer slides, 54 for one-line list slides, line spacing 0.95 to 1). Text boxes left 120, 840 wide, centred.
- Lists where every slide starts the same (like "✨ IN FOR OCTOBER:"): the heading sits on exactly the same line on every slide.
- A different photo on every slide where possible. Use the clinic's reception or team photos too, if they have them.
- The last slide has no swipe arrow.

## 4. Picture post: "I'm a simple girl…" (single image)

**Used for:** posts with a heading and three pictures, each with a short line underneath.
**Frances's reference:** "SKIN SURVIVAL- INFOGRAPHIC" (DAHXg290ZCE). Finished example: "Skin Survival: 8th October post" (DAHXg6cwGgE).

- Heading as in the template ("I'm a / *simple girl…*"), the plan's three lines under three pictures, each line starting with a capital letter.
- Pictures: frames about 264 x 330 at top 542, lefts 98, 408 and 718; lines 310 wide at top 900, centred under each picture.
- Each picture shows what its line says. Work out the picture for their niche and ask for it (see "Pictures" in the make-my-posts skill). Examples:
  - **Laser:** "Laser appointments as planned" = their laser machine; "The right prep and aftercare" = a razor, and a deodorant with a red cross; "Less time thinking about shaving" = a bikini.
  - **Lashes:** lash appointments = their lash tray and tweezers; aftercare = a lash brush, and mascara with a red cross; the payoff = an alarm clock (waking up ready).
  - **Teeth whitening:** appointments = their whitening light; aftercare = a toothbrush, and coffee with a red cross; the payoff = a camera (smiling in photos).
  - **Hair:** appointments = their colour bowl and brush; aftercare = their shampoo, and straighteners with a red cross; the payoff = a mirror.
- Cut each picture out of its background (Canva's background remover), so they float on the plain background. Busy treatment photos don't cut out cleanly: use a plain-background photo or an object instead.
- Red cross: a red (#E03131) X shape about 110 x 110 over the item the line says "no" to.

## The library's groups

Every style sits in one group on the post library page (`engine/post_library.json`, `categories`): **Review carousels**, **Treatment carousels**, **Before and after carousels**, **Single posts**, **Quote posts**, **Sale carousels**. A new style goes in the group that matches what the post is for. **Treatment carousels are named by their look, never their topic** (Frances, 2026-10-28: "it's the design of the carousel"; the words are always written fresh from the month's plan, so any design can promote any treatment). **Quote posts always have a plain background with dark words** (Frances, 2026-11-09), so a new quote design goes in with a flat colour behind its words, never a photo or pattern (see recipe 1).

**Model designs** (`"models": true` in `post_library.json`: recipes 13, 18, 20, 22 and 24). Their samples show Frances's own model shoot, which never goes on a student's post (Frances, 2026-11-09). Their own photo of a person first (them, their team, or a model they've worked with); only if they haven't got one, a stand-in model made with Canva's picture maker: a different-looking person for every post, the same person all the way through one post, in the same kind of shot as the sample, which they can keep or swap for their own (make-my-posts Step 4 has the wording, including the Instagram "AI info" label).

## 5. Swipe post (library: "One photo, big statements") (5 to 6 slides)

**Used for:** one big idea told slide by slide (how you work, why a consultation comes first).
**Frances's reference:** "SKIN SURVIVAL- SWIPE POST- MEMBERSHIP" (her copy DAHXheLZfx8). Library sample: "Your Clinic: swipe post (library sample)" (DAHXhfsNfJo).

- The same photo on every slide, at 55% over charcoal, not flipped.
- Each slide: a big serif statement (about 100, line spacing 0.92, box left 37.5, 1005 wide, top 846, three short lines) and an italic line under it (51, line spacing 1, box left 108, 864 wide, top 1164). The statement starts on the same line on every slide.
- The last slide is the call to action ("Ready to start? DM the word …") with no swipe arrow.

## 6. Elegant review carousel (10 slides)

**Used for:** client reviews with a softer, high-end look.
**Frances's reference:** "4 SKIN SURVIVAL- REVIEW CAROUSEL" (her copy DAHXhZhDEeE). Library sample: DAHXhUdvM0I.

- Same slide order and review rules as recipe 2. Headings sit inside a thin white outlined pill (630 x 78, left 225, 11 above the heading).
- Review slides 3 to 6: pill 229, heading 240, card 350 (610.5 x 564.4, left 235), story 960. Headings 58 (line spacing 0.92), body 40 (line spacing 1), boxes left 176, 728 wide.
- Take off the template's little grey and white blobs (they covered names in the old screenshots) and the see-through dark bands.
- Other slides: the heading, pill and words as one block, centred on the slide.

## 7. Skin education carousel (library: "Magazine cover") (9 slides)

**Used for:** teaching posts with a hook cover ("Your skin starts to look dull every winter… and here's why").
**Frances's reference:** "SKIN SURVIVAL- FACIAL CAROUSEL" (her copy DAHXhRqqJK4). Library sample: DAHXhcpczR0.

- Cover: words stacked down the right side, all right-aligned in a box left 120, 900 wide (small line, bigger line, huge word, small line, huge italic word), and "and here's why…" at the bottom right.
- Tip slides 2 to 8: a serif heading (73, line spacing 0.92) at top 880 and the explanation (44, line spacing 0.95) at top 975, both left 85 and 900 wide, so every tip starts on the same line.
- Last slide: "DM the word" and the keyword top right, with one short line under it.
- Careful wording: tips, not promises ("can help", "can make a real difference").

## 8. "Probably isn't for you" carousel (library: "Light and clean") (8 slides)

**Used for:** playful reverse-psychology posts about a treatment.
**Frances's reference:** "SKIN SURVIVAL- SKIN MEMBERSHIP CAROUSEL" (her copy DAHXheRD1Fw). Library sample: DAHXhT7d6Io.

- Cover and last slide: a photo at 50% over charcoal, three centred lines top right ("<Treatment>", "PROBABLY ISN'T FOR YOU", "if you enjoy…"). Take off the template's second photo layer.
- Middle slides: light background #E9E9E7, navy #172D5A words. Bold heading (78, two lines) at top 400 and the words (47) at top 614, both left 146, about 790 wide, so every slide lines up.
- Keep it light and cheeky, but never claim "pain free", "hair free" or how many sessions it takes. Say "a course of laser" and "less regrowth".

## 9. Sale teaser carousel (7 slides)

**Used for:** building excitement before a sale (Black Friday, a birthday sale).
**Frances's reference:** "SKIN SURVIVAL- SUMMER SALE CAROUSEL" (her copy DAHXhdK54GQ). Library sample: DAHXhtV_C9I.

- Every slide a photo at 55%, words centred in the middle: a line in capitals and an italic line under it. Cover: "We owe you an / APOLOGY…" low on the slide. Take off the template's cut-out photo layer on the cover.
- Story: the apology, "for making you wait this long for <sale>", "you've seen our offers before… but nothing like this", what's coming, "opens soon", "spaces are limited", then "Comment WAITLIST".
- No prices or percentages unless the student gives them, and never invent a discount.

## 10. Sale waitlist carousel (8 slides)

**Used for:** asking people to join a sale waitlist.
**Frances's reference:** "SKIN SURVIVAL- WAITLIST CAROUSEL" (her copy DAHXhVEwsLw). Library sample: DAHXhsNq1D4.

- Every slide: a photo at 40% over charcoal, a big serif heading top left (115, line spacing 0.9, box left 100, 880 wide, top 160) and a short paragraph straight under it (48, line spacing 0.95, 720 wide, 40 below the heading). The heading starts on the same line on every slide.
- Story: the hook, "we only do this once a year", first access, why now, a thank you to loyal clients, what happens when the waitlist closes, no hints yet, "Comment WAITLIST".

## 11. Sale review carousel (10 slides)

**Used for:** reviews while a sale is live.
**Frances's reference:** "3 SKIN SURVIVAL- REVIEW CAROUSEL (Summer Sale edition)" (her copy DAHXhUmwOKs). Library sample: DAHXhjy5oOY.

- Cover: the sale name big at the top left, a short line under it, and one review card below (520 wide, left 84, top 440).
- Slides 2 to 6 as recipe 6 (the template's review screenshots and the blobs over names are replaced with review cards from `review_card.py`).
- Slides 7 to 10: "If you've been waiting for the right time…", "This week only…", "Why you can't miss this", and the DM call to action, each as one centred block with its heading in an outlined pill. Take off the see-through dark bands.
- Offer details (prices, percentages, dates) only from the student, never made up.

## 12. Concern carousel (library: "Words at the top") (9 slides)

**Used for:** any treatment post (the example spoke to PCOS; the words always come from the month's plan).
**Frances's reference:** "SKIN SURVIVAL- PCOS" (her copy DAHZTebLwI4). Library sample: "Post library sample: concern carousel" (DAHZTU6gBzw).

- Every slide: a treatment photo at 40 to 60% over charcoal, a bold heading (62) with a normal line or two under it (46), both centred, at the top of the slide. Cover: a big stat (111) with a short white underline under the key word, then one bold line (56).
- Story: the stat, how it shows up day to day, what living with it feels like, "you don't have to just live with it", the treatments the clinic offers for it (a list), a plan built around them, "imagine…", then "DM <KEYWORD>".
- No prices or percentages unless the student gives them; results vary, never promised.

## 13. Awareness month carousel (library: "Elegant pills") (10 slides)

**Used for:** any treatment post (the example was an awareness month; the words always come from the month's plan).
**Frances's reference:** "SKIN SURVIVAL- SWIPE POST- PCOS" (her copy DAHZTWElAgI). Library sample: "Post library sample: awareness month carousel" (DAHZTfb3V2Q).

- Every slide: a photo at 45 to 60% over charcoal, words centred in the middle: a serif heading in capitals (49 to 82), an italic line under it (39), and lists or key lines in thin white outlined pills (33).
- Story: the awareness month and a stat, what it can cause (pills), how people feel, the areas it affects (pills), why it matters, what the treatment can do (pills, careful wording: reduce, not remove), course and top-ups, what the clinic offers (pills), "this awareness month…", then the DM call to action.
- No prices or percentages unless the student gives them.

## 14. Best time to start carousel (library: "Numbered light slides") (9 slides)

**Used for:** any treatment post with numbered points (the example gave reasons to start laser early; the words always come from the month's plan).
**Frances's reference:** "SKIN SURVIVAL- LASER CAROUSEL" (her copy DAHZTQLSoK8). Library sample: "Post library sample: best time to start carousel" (DAHZTdQX4Bs).

- Cover and last slide: a photo at 48% over charcoal with centred capitals at the top (54) and the treatment in big italic capitals (87).
- Reason slides: light background (#E9E9E7, or the student's lightest colour), a bold numbered heading in capitals (64) and the reason under it (47), both left 160, navy (or the student's darkest colour), sitting just above the middle. The heading starts on the same line on every slide.
- Careful wording: "slower regrowth", "smoother", never "hair free"; results vary.

## 15. Before and after carousel (library: "Split-screen results") (8 slides)

**Used for:** before and after posts (the plan's "client results" or "before and after" posts).
**Frances's reference:** "CLIENT RESULTS CAROUSEL" (her copies DAHZTgvqRIc and DAHadIaWb0w). Library sample: "Post library sample: before and after carousel" (DAHadGNKD7g). The sample keeps the template's empty photo frames on purpose (Frances, 2026-11-09: "they'll understand with before and afters what goes where"), so never write "before" or "after" labels into the frames.

- **Only their own before and after photos of their own clients** (Frances, 2026-11-09). Ask for them in plain words when the post is picked: at least five pairs, each taken in the same light and from the same angle. Never use photos from another clinic, the internet, a product company or a stock site, never make or change a before or after picture (no AI, no filters, no retouching), and never put words over a result. If they haven't got five pairs, use as many as they have and take out the spare result slides; with none, offer a different design for that day.
- UK advertising rules: before and after photos must be genuine, unedited and typical of what clients get (`content-plans/niche-rules.md`). Only use pairs the client has agreed can be shared (their content model consent).
- Cover: a clinic photo at 60% over black; the heading at the top (51, centred), one result in the frame in the middle (509 x 636: the after photo, or the before and after side by side if they have one picture showing both), a line under it (34) and the arrow bottom right.
- Result slides 2 to 6 take turns: two frames stacked (1080 x 675 each: before on top, after underneath) and two frames side by side (540 x 1350 each: before on the left, after on the right). One pair per slide, the handle bottom left.
- Slide 7: a photo of them or their team at 48% over black with the dark fade at the bottom; heading (51) and words (37) centred low on the slide.
- Slide 8: a clinic photo at 54% with the dark fade; "DM the word …" (62) and one line about booking a consultation (39).
- Careful wording: results vary from person to person; never promise the same result ("work towards results like these", not "get these results").

## 16. Zoom in for a sign (library: "Zoom in for a sign") (single image)

**Used for:** the "zoom in for a sign" trend, or any single post that nudges people to book.
**Frances's reference:** "SKIN SURVIVAL- ZOOM IN TREND" (her copy DAHadGDOYCg). Library sample: "Post library sample: zoom in for a sign post" (DAHadA1sQVc).

- Keep the look exactly: light background (#E9E9E7, or the student's lightest colour), "ZOOM IN / for a / SIGN" in bold at the top in navy (or their darkest colour), the hand photo, the handle bottom left.
- The tiny words between the finger and thumb are the only words that change: one short line in their voice, two even lines at most (about 35 letters), so they fit between the fingers. Keep it a playful nudge ("It's time to book that facial girl 👀"), never a result or a promise.

## 17. Crossed-out excuses carousel (library: "Crossed-out excuses") (8 slides)

**Used for:** any treatment post about the reasons people put off booking (the example was a glass skin facial; the words always come from the month's plan).
**Frances's reference:** "SKIN SURVIVAL- CAROUSEL WITH VIDEOS- GLASS SKIN FACIAL" (her copy DAHadD3SAkw). Library sample: "Post library sample: crossed-out excuses carousel" (DAHadPhprY8).

- Every slide: two treatment photos (or clips: the template takes videos too), top half and bottom half, at 60% over charcoal.
- Top: the excuse, white, 46, centred around 310 from the top, with a thin white line drawn through it. **The line's length must match the excuse's width** (resize it to the text width plus a little either side), so it always looks hand-crossed-out.
- Bottom: the new thinking, white, 46, centred around 985. One line each where possible; never a word on its own line.
- Eight excuse and answer pairs, in the clinic's voice. Careful wording: no promises or results.

## 18. Notes app answers carousel (library: "Notes app answers") (12 slides)

**Used for:** FAQ posts for any treatment (the example was laser hair removal; the questions and answers always come from the month's plan).
**Frances's reference:** "SKIN SURVIVAL- LASER FAQ CAROUSEL" (her copy DAHadK3IrEw). Library sample: "Post library sample: notes app FAQ carousel" (DAHadBcBD74).

- Every slide: one photo at 60% over charcoal, the same photo on every slide, with a Notes-style screenshot in the middle (about 613 wide, centred) and the handle and arrow at the bottom.
- **The screenshots are pictures, so Canva can't change their words.** The engine draws a new one for each slide: write `cards.json` (one card a slide: `{"heading": "“Does it hurt?”", "words": "..."}`, the first with `"title": true`), run `engine/notes_card.py cards.json --out <folder>`, and put each card in the screenshot's place, 613 wide and centred, at the height the file name gives (white card, the Notes top bar, the question in bold quotes, then the answer; a blank line starts a new paragraph).
- Slides: a title card ("<TREATMENT> FAQS" and a short line), ten question cards, and a last card with the DM call to action.
- Careful wording in every answer (`content-plans/niche-rules.md`): never "permanent", "gone for good", percentages, "safe for all skin tones" or "doesn't cause scarring"; say a consultation and patch test come first and results vary. The template's own answers are only an example and never go on a student's post.

## 19. Review bubbles carousel (library: "Review bubbles") (11 slides)

**Used for:** client review carousels.
**Frances's reference:** "SKIN SURVIVAL- REVIEW CAROUSEL" (her copy DAHadOlP7sM). Library sample: "Post library sample: review bubbles carousel" (DAHadMNSHck), made with the made-up reviews in `engine/library/sample-reviews.md`.

- **The reviews are drawn by the engine, never screenshots of someone else's reviews:** `engine/review_bubble.py bubble <reviews.md> "<name>" ... --width 632 --out <folder>` makes one white bubble per review (five gold stars, the exact words, one shared text size) and prints the size to give each in Canva. `engine/review_bubble.py phone ... --clinic "<clinic>" --photo <clinic photo>` makes the phone's Notification Centre screen ("New review for <clinic>" from Google, one per review).
- Slide 1: a photo of them holding a phone or tablet at full strength, "I've got a text!!!" at the top.
- Slide 2: the phone frame with the drawn notification screen inside it; "Swipe to see what our amazing clients have said about us recently…" under it.
- Slides 3 to 8: a team photo at 54% over charcoal; one or two bubbles 632 wide, centred (left 224), stacked 15 apart, the stack centred around 675 from the top. Resize each picture box to the bubble's size and set its crop to the whole picture (Canva keeps the old zoom otherwise). Take off the template's little white pills (they hid names on the old screenshots).
- Slide 9: "AT <CLINIC NAME>" in the outlined pill, three short paragraphs in their voice. Slide 10: "IF YOU ARE…" with three pain points for their treatments and "We are the clinic for you." Slide 11: "DM the word …".
- Review rules: their own 5-star reviews only, never changed, first name and initial, never one that claims a result (number of sessions, "results straight away", "pain free").

## 20. Bright sale countdown carousel (library: "Bright sale countdown") (7 slides)

**Used for:** sale waitlist posts before a seasonal sale (summer, Black Friday, a birthday sale).
**Frances's reference:** "SKIN SURVIVAL- SUMMER SALE WAITLIST CAROUSEL" (her copy DAHadD2dARs). Library sample: "Post library sample: sale coming soon carousel" (DAHadMUteUA).

- White background, a bright photo faded to about 34% (cover 65%, standing to the right), charcoal serif capitals; a soft light-yellow glow behind the key words on the cover and the call to action (the template's duplicated text layers make the glow: change both copies).
- Cover: the clinic's name small at the top (in place of a logo), "THE / <SEASON> / SALE / IS COMING…", then a line about the offer and "PLUS an extra little surprise…".
- Slides 2 to 6: a big heading (73 to 92) with a smaller line under it (51 to 58), centred around the middle. Slide 7: "Comment "WAITLIST"" left-aligned, big, with two short paragraphs under it.
- No prices or percentages unless the student gives them; never "hair free" (say "smoother skin"), never body-shape promises ("snatched", inches); the sale date comes from them.

## 21. Big reveal carousel (library: "Big reveal") (10 slides)

**Used for:** launching a new treatment (the example was wood therapy lymphatic drainage; the words always come from the month's plan).
**Frances's reference:** "SKIN SURVIVAL- LAUNCHING WOOD THERAPY" (her copy DAHadOYPcnc). Library sample: "Post library sample: new treatment launch carousel" (DAHadbze240).

- Every slide: a photo or clip at 42 to 60% over charcoal; headings in bold serif capitals in a soft yellow (#FBFCBB, or the student's lightest accent colour), the rest white. Headings sit at the top, centred or left-aligned as in the template.
- Story: "We've been keeping a secret! / NEW TREATMENT AVAILABLE NOW…", what it combines (a list), "Introducing… <TREATMENT>", "If you've been seeing everyone talking about…", "So what actually IS…" (what it helps with), "And no… it's not just a trend", "This treatment is PERFECT if you:" (a list), the offer (optional), and "COMMENT "<KEYWORD>"".
- Careful wording: no body-shape or medical claims (no "sculpt", "snatched", "contour", "post-surgery"); say "feel lighter", "help with bloating", "support circulation". No prices or percentages unless the student gives them, and never pressure to book fast.

## 22. "We probably shouldn't…" sale carousel (library: "We probably shouldn't…") (8 slides)

**Used for:** sale waitlist posts, especially when a new treatment launches with the sale.
**Frances's reference:** "SKIN SURVIVAL- SUMMER SALE WAITLIST CAROUSEL" (her copy DAHadDaYIlM, the grey one). Library sample: "Post library sample: we probably shouldn't sale carousel" (DAHadfAPNO4).

- Soft grey background (#AAAAAA, or the student's mid colour), white serif capitals with key words in bold light yellow (#FBFCBB, or their lightest accent); the clinic's name small and centred at the very top of every slide (in place of a logo).
- Photos are cut-outs standing at the bottom of the slide below the words. Canva's background remover isn't available through the connector, so when a photo needs cutting out and has a plain background, the engine cuts it out itself (key out the background colour, as done for the sample) and uploads the cut-out. Never use photos showing another business's logo (uniforms, signs).
- Story: "We probably SHOULDN'T be doing this…", what's dropping, "this is the one you want to be ready for", the new treatment, the glow-up feeling, waitlist perks, "the best slots go fast", "Comment "WAITLIST"".
- No prices or percentages unless the student gives them; never "hair free" (say "smoother skin"); no body-shape promises ("snatched", "sculpted").

## 23. The important meeting carousel (library: "The important meeting") (5 slides)

**Used for:** a playful post showing several treatments (one per slide), or one treatment repeated across slides.
**Frances's reference:** "SKIN SURVIVAL- MEETING CAROUSEL TREND" (her copy DAHadHBt3RA). Library sample: "Post library sample: the meeting carousel" (DAHadY6Igtw).

- Every slide: a treatment photo at 54 to 63% over charcoal, ""I have an important meeting I can't miss"" (76, white, centred around 380), "THE MEETING:" under it (76), and a calendar booking card under that (about 700 x 280, centred, top around 690).
- **The calendar cards are pictures**, so the engine draws each one: write `meetings.json` (`[{"treatment": "HydraFacial", "emoji": "🫧", "start": "12:00"}, ...]`), run `engine/calendar_card.py meetings.json --out <folder>`, and put each card in the card's place (700 x 280, centred). One treatment per slide, from the clinic's own treatment list, with a different time on each.
- Use a photo of that treatment on each slide; never a photo showing another business's name (headbands, uniforms).

## 24. Soft statements carousel (library: "Soft statements") (9 slides)

**Used for:** "how <treatment> makes your everyday life easier" posts, or any list of everyday moments for a treatment.
**Frances's reference:** "SKIN SURVIVAL- LASER CAROUSEL" (her copy DAHadN_x8Io; the earlier copy DAHZTSUpsC0 is the same design). Library sample: "Post library sample: everyday life easier carousel" (DAHaddaKkuw).

- Cover: a photo at 48% over charcoal, a big italic serif title top left (121) and a plain line under it (57).
- Middle slides: the same photo at 40% on every slide, a bold heading (64) and one to three short lines under it (47), centred in the middle of the slide.
- Last slide: a photo at 49%, "DM the word "<KEYWORD>"" (79) and a line under it, top right.
- Careful wording: "fewer ingrown hairs", "less shaving", never "no more hair" or "hair free"; no made-up client quotes ("most clients say…").

## 25. Hand-drawn underline carousel (library: "Hand-drawn underline") (10 slides)

**Used for:** explaining any treatment and its benefits (the example was wood therapy lymphatic drainage; the words always come from the month's plan).
**Frances's reference:** "SKIN SURVIVAL- LYMPHATIC EDUCATIONAL CAROUSEL" (her copy DAHadY5GALs). Library sample: "Post library sample: lymphatic education carousel" (DAHadfAgkWg).

- Every slide: a photo over charcoal (cover 60%, middle slides 31% to 49%), white bold serif words, centred, the handle bottom left and the arrow bottom right.
- Cover: a big heading (111, two lines) with the hand-drawn white line under its last words (move the line so it sits under the words that matter), and a smaller bold line under it (56).
- Slide 2: a bold heading top left (62) with the problem under it in plain words (46). Slide 3: what the treatment does (62 bold) and what that means for them (46).
- Benefit slides: the same photo on each (tools, products or the room), a bold benefit in the middle (78) and one or two lines under it (46). The heading starts on the same line on every benefit slide.
- Second to last: the big idea (78 bold) and a line under it, at the top. Last slide: a question (46), "Comment "<WORD>"" (74 bold) and what they'll get.
- Careful wording (`content-plans/niche-rules.md`): "can", "may", "helps", "the appearance of"; never promise fat loss, inches or permanent results; never speak for clients ("our clients notice…"); "everyone's different".
- Use a photo of that treatment on every slide, never one showing another business's name (uniforms, towels, headbands): move or zoom the photo until it's out of shot, or use another.
