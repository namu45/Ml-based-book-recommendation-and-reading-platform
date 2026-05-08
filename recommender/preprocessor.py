# recommender/preprocessor.py
import re

# small list of short words we DO NOT want to accidentally glue when fixing broken words
_SHORT_WORDS = {
    'of','to','in','on','by','for','and','the','a','an','is','it','or','as','be',
    'we','he','she','they','you','are','was','were','this','that','with','at','from'
}

def _remove_gutenberg_markers(text):
    """Strip common Project Gutenberg start/end markers (many variants)."""
    # start marker (keep anything after the marker)
    start_re = re.compile(
        r'\*\*\*\s*START OF (THIS|THE)?\s*PROJECT GUTENBERG EBOOK.*?\*\*\*',
        re.IGNORECASE | re.DOTALL
    )
    end_re = re.compile(
        r'\*\*\*\s*END OF (THIS|THE)?\s*PROJECT GUTENBERG EBOOK.*?\*\*\*',
        re.IGNORECASE | re.DOTALL
    )

    m_start = start_re.search(text)
    m_end = end_re.search(text)

    if m_start and m_end and m_end.start() > m_start.end():
        return text[m_start.end():m_end.start()]
    if m_start:
        return text[m_start.end():]
    if m_end:
        return text[:m_end.start()]

    # if none of the explicit markers found, fall back to removing big header blocks
    # Remove leading boilerplate until first big paragraph (heuristic)
    parts = re.split(r'\n{3,}', text, maxsplit=1)
    if len(parts) > 1:
        return parts[1]
    return text


def _strip_boilerplate_paragraphs(text):
    """
    Remove paragraphs that are clearly boilerplate: mention Gutenberg, Produced by,
    Transcriber's Note, copyright/legalese, license, distributed by, etc.
    We operate per-paragraph so we avoid deleting story text accidentally.
    """
    paragraphs = re.split(r'\n{2,}', text)
    keep = []
    bad_pat = re.compile(
        r'(project gutenberg|produced by|transcrib|copyright|distributed by|gutenberg-tm|license|public domain|this ebook|illustrator)',
        re.IGNORECASE
    )
    for p in paragraphs:
        if not p.strip():
            continue
        # if paragraph contains clear boilerplate terms -> drop it
        if bad_pat.search(p):
            continue
        keep.append(p)
    return '\n\n'.join(keep)


def _normalize_paragraph(paragraph):
    """
    For a single paragraph:
     - split into lines,
     - remove trailing/leading spaces from each line,
     - if a line ends with hyphen '-' => remove hyphen and join to next without space,
     - otherwise join lines with a single space (this removes forced line wraps),
     - post-process: remove spaces before punctuation, collapse multiple spaces,
     - heuristic: if a single-letter continuation remains (e.g. 'ceilin g') glue that single letter to the previous token
       (we only glue single-letter tokens — low risk, fixes many hyphen-loss cases).
    """
    lines = [ln.rstrip() for ln in paragraph.split('\n') if ln.strip() != '']
    if not lines:
        return ''

    out_parts = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.endswith('-'):
            # remove trailing hyphen and concatenate with next line directly (no space)
            line = line[:-1]
            next_line = lines[i+1].lstrip() if i+1 < len(lines) else ''
            # join without a space
            combined = line + next_line
            out_parts.append(combined)
            i += 2  # consumed two lines
            continue
        else:
            # normal join: append and add a space between pieces
            out_parts.append(line)
            i += 1

    # join parts with single spaces
    joined = ' '.join(out_parts).strip()

    # fix space before punctuation: "word ." -> "word."
    joined = re.sub(r'\s+([,.;:!?%)]})', r'\1', joined)

    # glue single letter continuations that look like broken word halves:
    # pattern: word (4+ letters) + single-letter token => glue: "ceilin g" => "ceiling"
    joined = re.sub(
        r'(\b[a-zA-Z]{4,})\s+([a-zA-Z])\b',
        lambda m: (m.group(1) + m.group(2)) if m.group(2).lower() not in _SHORT_WORDS else m.group(0),
        joined
    )

    # collapse multiple spaces
    joined = re.sub(r'\s{2,}', ' ', joined)
    return joined


def preprocess_book(file_path, words_per_page=500):
    """
    Read a plaintext Gutenberg-style file, remove headers/footers and boilerplate,
    normalize text and join wrapped lines, then split into pages of roughly words_per_page words.
    Returns a list of pages, each page is a list of paragraph dicts: {'type':..., 'text':...}
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()
    except Exception:
        return []

    # remove BOM if present
    if raw_text.startswith('\ufeff'):
        raw_text = raw_text.lstrip('\ufeff')

    # ---- remove explicit Gutenberg markers if present ----
    main = _remove_gutenberg_markers(raw_text)

    # ---- remove bracketed transcriber's notes anywhere ----
    main = re.sub(r'\[Transcrib(er|or).*?\]', '', main, flags=re.IGNORECASE | re.DOTALL)

    # ---- strip obvious boilerplate paragraphs that mention Gutenberg/copyright/etc ----
    main = _strip_boilerplate_paragraphs(main)

    # ---- normalize line endings and remove accidental CRs ----
    main = main.replace('\r\n', '\n').replace('\r', '\n')

    # ---- collapse excessive blank lines (no more than two between paragraphs) ----
    main = re.sub(r'\n{3,}', '\n\n', main).strip()

    # ---- normalize fancy quotes/dashes to plain ASCII equivalents (optional but helps) ----
    main = main.replace('“', '"').replace('”', '"').replace('—', ' - ').replace('–', '-')
    main = main.replace('’', "'").replace('‘', "'")

    # ---- split into paragraphs (by blank line) and normalize each paragraph ----
    raw_paras = [p for p in re.split(r'\n{2,}', main) if p.strip()]
    normalized_paras = []
    for p in raw_paras:
        np = _normalize_paragraph(p)
        if np:
            normalized_paras.append(np)

    # ---- convert paragraphs into dicts with type markers ----
    processed_paragraphs = []
    for para in normalized_paras:
        if para.startswith('"') or para.startswith('“'):
            ptype = 'dialogue'
        elif len(para) < 60 and para.isupper():
            ptype = 'section'
        else:
            ptype = 'normal'
        processed_paragraphs.append({'type': ptype, 'text': para})

    # ---- paginate by approximate word counts ----
    pages = []
    current_page = []
    word_count = 0
    for para in processed_paragraphs:
        para_words = len(para['text'].split())
        # if adding this paragraph would exceed the word limit and current_page has content -> start new page
        if current_page and (word_count + para_words > words_per_page):
            pages.append(current_page)
            current_page = []
            word_count = 0
        current_page.append(para)
        word_count += para_words
    if current_page:
        pages.append(current_page)

    return pages
