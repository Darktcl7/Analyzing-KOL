import docx

def read_docx(file_path):
    doc = docx.Document(file_path)
    for i, para in enumerate(doc.paragraphs[:68]):
        text = para.text.strip()
        if text:
            print(f"Para {i}: {text}")

if __name__ == "__main__":
    read_docx(r"D:\Django Project\KOL_Scouting_Project\proposal\68a817ce054d7.docx")
