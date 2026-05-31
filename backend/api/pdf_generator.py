import os
import re
from fpdf import FPDF
from pathlib import Path

class ForensicPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_margins(20, 20, 20)
        self.set_auto_page_break(auto=True, margin=20)
        
    def header(self):
        if self.page_no() > 1:
            self.set_font("helvetica", "I", 8)
            self.set_text_color(100, 100, 100)
            self.cell(0, 10, "TATVA FORENSIC INTELLIGENCE REPORT", align="L")
            self.cell(0, 10, f"Page {self.page_no()}", align="R")
            self.ln(10)
            self.set_draw_color(200, 200, 200)
            self.line(20, self.get_y(), 190, self.get_y())
            self.ln(5)

    def footer(self):
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_font("helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 10, "CONFIDENTIAL - LAW ENFORCEMENT & INTERNAL USE ONLY", align="C")

    def build_title_page(self, title, case_id):
        self.add_page()
        # Top banner line
        self.set_fill_color(0, 51, 84) # Dark Navy #003354
        self.rect(0, 0, 210, 40, "F")
        
        self.set_y(50)
        self.set_font("helvetica", "B", 26)
        self.set_text_color(0, 51, 84)
        self.multi_cell(0, 12, "TATVA FORENSIC ANALYSIS", align="C")
        
        self.set_y(80)
        self.set_font("helvetica", "B", 18)
        self.set_text_color(254, 183, 0) # Amber #feb700
        self.multi_cell(0, 10, title.upper(), align="C")
        
        # Decorative line
        self.set_y(100)
        self.set_draw_color(0, 51, 84)
        self.line(40, self.get_y(), 170, self.get_y())
        
        self.set_y(120)
        self.set_font("helvetica", "", 12)
        self.set_text_color(60, 60, 60)
        self.cell(0, 8, f"CASE ID: {case_id}", align="C", new_x="LMARGIN", new_y="NEXT")
        import datetime
        self.cell(0, 8, f"GENERATED ON: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 8, "CLASSIFICATION: CONFIDENTIAL", align="C", new_x="LMARGIN", new_y="NEXT")
        
        # Meta info box at the bottom
        self.set_y(220)
        self.set_fill_color(245, 245, 245)
        self.set_draw_color(220, 220, 220)
        self.rect(20, 210, 170, 40, "DF")
        self.set_y(215)
        self.set_font("helvetica", "B", 10)
        self.set_text_color(0, 51, 84)
        self.cell(0, 6, "  INVESTIGATION UNIT:", new_x="LMARGIN", new_y="NEXT")
        self.set_font("helvetica", "", 10)
        self.set_text_color(60, 60, 60)
        self.cell(0, 6, "  TATVA Digital Forensics & Cyber Intelligence Division", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 6, "  All source evidence corroboration & risk analysis computed dynamically.", new_x="LMARGIN", new_y="NEXT")

def markdown_to_pdf(markdown_str: str, output_path: str, case_id: str):
    pdf = ForensicPDF()
    pdf.build_title_page("Case Investigation Findings", case_id)
    pdf.add_page()
    pdf.set_y(20)
    
    # Simple parser for markdown lines
    lines = markdown_str.split("\n")
    in_code_block = False
    code_content = []
    
    for line in lines:
        stripped = line.strip()
        
        # Check code block
        if stripped.startswith("```"):
            if in_code_block:
                # Close code block
                in_code_block = False
                pdf.set_font("courier", "", 9)
                pdf.set_fill_color(248, 248, 248)
                pdf.set_text_color(30, 30, 30)
                code_text = "\n".join(code_content)
                # Split code text to avoid overflow
                pdf.multi_cell(0, 5, code_text, border=1, fill=True)
                pdf.ln(5)
                code_content = []
            else:
                in_code_block = True
            continue
            
        if in_code_block:
            code_content.append(line)
            continue
            
        # Headers
        if stripped.startswith("# "):
            title_text = stripped[2:].strip()
            pdf.ln(8)
            pdf.set_font("helvetica", "B", 20)
            pdf.set_text_color(0, 51, 84)
            pdf.multi_cell(0, 10, title_text)
            pdf.ln(4)
            
        elif stripped.startswith("## "):
            h2_text = stripped[3:].strip()
            pdf.ln(6)
            pdf.set_font("helvetica", "B", 14)
            pdf.set_text_color(0, 51, 84)
            pdf.multi_cell(0, 8, h2_text)
            # Line under h2
            pdf.set_draw_color(0, 51, 84)
            pdf.line(20, pdf.get_y() + 1, 190, pdf.get_y() + 1)
            pdf.ln(4)
            
        elif stripped.startswith("### "):
            h3_text = stripped[4:].strip()
            pdf.ln(4)
            pdf.set_font("helvetica", "B", 11)
            pdf.set_text_color(254, 183, 0)
            pdf.multi_cell(0, 6, h3_text)
            pdf.ln(2)
            
        # Bullet list items
        elif stripped.startswith("* ") or stripped.startswith("- "):
            bullet_text = stripped[2:].strip()
            pdf.set_font("helvetica", "", 10)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(5, 5, chr(149), align="L") # bullet symbol
            pdf.multi_cell(0, 5, bullet_text)
            pdf.ln(2)
            
        # Numbered list items
        elif re.match(r"^\d+\.\s", stripped):
            match = re.match(r"^(\d+)\.\s(.*)", stripped)
            num = match.group(1)
            item_text = match.group(2).strip()
            pdf.set_font("helvetica", "", 10)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(8, 5, f"{num}.", align="L")
            pdf.multi_cell(0, 5, item_text)
            pdf.ln(2)
            
        # Standard paragraphs
        elif stripped:
            # Check for bold formatting in text (**bold**)
            # We can simplify by just printing the text, but let's replace **bold** with bold representation in PDF
            clean_text = stripped.replace("**", "")
            pdf.set_font("helvetica", "", 10)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 5, clean_text)
            pdf.ln(3)
            
        else:
            pdf.ln(2)
            
    pdf.output(output_path)
    print(f"[PDF Generator] Saved PDF report to {output_path}")
