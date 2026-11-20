#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Generate the Cobalt CV from the existing resume-zella LaTeX format."""

import argparse
from html import escape
from os.path import relpath
from pathlib import Path
import re
from string import Template
from urllib.parse import quote, urlsplit


def argument(text, pos):
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos == len(text) or text[pos] != "{":
        raise ValueError("Expected a braced LaTeX argument")
    depth = 0
    for match in re.finditer(r"\\.|[{}]", text[pos:]):
        if match[0] == "{":
            depth += 1
        elif match[0] == "}":
            depth -= 1
            if depth == 0:
                return text[pos + 1:pos + match.start()], pos + match.end()
    raise ValueError("Unclosed LaTeX argument")


def plain(text):
    if any(char in text for char in "{}$"):
        raise ValueError(f"Unsupported LaTeX text: {text!r}")
    return escape(text.replace("``", "“").replace("''", "”")).replace("~", "&nbsp;")


def inline(text):
    text = text.replace(r"$\cdot$", "·")
    wrappers = {"textbf": "strong", "textit": "em", "emph": "em", "code": "code", "texttt": "code"}
    result, pos = [], 0
    for match in re.finditer(r"\\([A-Za-z]+|.)", text):
        if match.start() < pos:
            continue
        result.append(plain(text[pos:match.start()]))
        command, pos = match[1], match.end()
        if command in wrappers or command in ("href", "textls"):
            value, pos = argument(text, pos)
            if command == "href":
                label, pos = argument(text, pos)
                url = value.replace(r"\_", "_").replace(r"\%", "%")
                if urlsplit(url).scheme not in ("https", "http", "mailto", "tel"):
                    raise ValueError(f"Unsupported link destination: {url!r}")
                result.append(f'<a href="{escape(url, quote=True)}">{inline(label)}</a>')
            elif command == "textls":
                result.append(inline(value))
            else:
                tag = wrappers[command]
                result.append(f"<{tag}>{inline(value)}</{tag}>")
        elif command in "&_%#$}{":
            result.append(escape(command))
        else:
            raise ValueError(f"Unsupported LaTeX command: \\{command}")
    result.append(plain(text[pos:]))
    return re.sub(r"\s+", " ", "".join(result)).strip()


def sections(body):
    body = re.sub(r"\\(?:begin|end)\{itemize\}(?:\[[^\]]*\])?|\\resumeItemList(?:Start|End)\b", "", body)
    pattern = r"\\begin\{rSection\}\{([^{}]+)\}(.*?)\\end\{rSection\}"
    if re.sub(pattern, "", body, flags=re.S).strip() or not re.search(pattern, body, re.S):
        raise ValueError("Expected rSection blocks containing resumeEntry and resumeItem commands")
    result = []
    for number, match in enumerate(re.finditer(pattern, body, re.S), 1):
        title, content = match.groups()
        entries, pos = [(None, None, [])], 0
        while content[pos:].strip():
            command = re.match(r"\s*\\(resumeEntry|resumeItem)\b", content[pos:])
            if not command:
                raise ValueError(f"Unsupported content in section {title!r}")
            value, pos = argument(content, pos + command.end())
            if command[1] == "resumeEntry":
                date, pos = argument(content, pos)
                entries.append((inline(value), inline(date), []))
            else:
                entries[-1][2].append(inline(value))
        lines = [f'<section class="cv-section" aria-labelledby="cv-section-{number}">', f'  <h2 id="cv-section-{number}">{inline(title)}</h2>', '  <div class="cv-section-content">']
        for title, date, items in entries:
            if title:
                lines.extend(['    <article class="cv-entry">', '      <header class="cv-entry-heading">', f"        <h3>{title}</h3>", f'        <p class="cv-date">{date}</p>', '      </header>'])
            if items:
                lines.extend(['      <ul class="cv-bullets">', *[f"        <li>{item}</li>" for item in items], '      </ul>'])
            if title:
                lines.append('    </article>')
        lines.extend(['  </div>', '</section>'])
        result.extend("        " + line for line in lines)
    return "\n".join(result)


def render(source, output, pdf_output):
    source = re.sub(r"\\.|%[^\n]*\n?", lambda m: "" if m[0].startswith("%") else m[0], source)
    document = re.fullmatch(r"(.*?)\\begin\{document\}(.*?)\\end\{document\}\s*", source, re.S)
    if not document:
        raise ValueError("Expected a complete LaTeX document")
    fields = {}
    for key in ("name", "address"):
        match = re.search(r"\\" + key + r"\b", document[1])
        if not match:
            raise ValueError(f"Missing \\{key}")
        fields[key] = inline(argument(document[1], match.end())[0])
    site = Path(__file__).resolve().parents[1]
    url = lambda path: quote(Path(relpath(path.resolve(), output.resolve().parent)).as_posix())
    name = re.sub(r"<[^>]+>", "", fields["name"])
    template = Path(__file__).with_name("cv-template.html").read_text(encoding="utf-8")
    return Template(template).substitute(fields, meta_name=escape(name, quote=True), page_name=name, sections=sections(document[2]), stylesheet=url(site / "cobalt.css"), home=url(site / "index.html"), writing=url(site / "writing.html"), public_key=url(site / "publickey.asc"), cv=quote(output.name), pdf=url(pdf_output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("input", "pdf", "output", "pdf-output"):
        parser.add_argument(f"--{flag}", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.input.suffix.lower() != ".tex" or args.output.suffix.lower() != ".html" or args.pdf_output.suffix.lower() != ".pdf":
            raise ValueError("Expected a .tex input, .html output, and .pdf download output")
        if any(not path.parent.is_dir() for path in (args.output, args.pdf_output)):
            raise ValueError("Output directories must already exist")
        html = render(args.input.read_text(encoding="utf-8"), args.output, args.pdf_output)
        pdf = args.pdf.read_bytes()
        if not pdf.startswith(b"%PDF-"):
            raise ValueError("The input PDF is not a PDF document")
        args.output.write_text(html, encoding="utf-8")
        if args.pdf.resolve() != args.pdf_output.resolve():
            args.pdf_output.write_bytes(pdf)
    except (OSError, ValueError) as error:
        parser.exit(1, f"CV generation failed: {error}\n")
    print(f"Generated {args.output}; PDF: {args.pdf_output}")


if __name__ == "__main__":
    main()
