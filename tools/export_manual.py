"""Writes a PDF from a Markdown manual, one PDF page per page marker.

  python -m tools.export_manual manual/adn1.md
"""

import re
import sys
from pathlib import Path

from fpdf import FPDF

from common.config import ROOT
from services.knowledge.parse import split_markdown

DEFAULT = ROOT / "manual" / "vdn1.md"
WIDTH = 170
SIZES = {"#": 18, "##": 14, "###": 12}


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    target = source.with_suffix(".pdf")
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_margin(20)
    for _, text in split_markdown(source.read_text()):
        pdf.add_page()
        for line in text.splitlines():
            line = line.rstrip()
            heading = re.match(r"^(#{1,3})\s+(.*)$", line)
            if heading:
                pdf.set_font("Helvetica", "B", SIZES[heading.group(1)])
                pdf.ln(3)
                pdf.multi_cell(WIDTH, 8, heading.group(2), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(1)
            elif re.match(r"^\|[\s-]+\|", line):
                continue
            elif line:
                pdf.set_font("Helvetica", "", 11)
                pdf.multi_cell(WIDTH, 6, line, new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.ln(2)
    pdf.output(str(target))
    print(f"wrote {target} with {pdf.page_no()} pages")


if __name__ == "__main__":
    main()
