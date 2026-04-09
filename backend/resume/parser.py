"""
Parses uploaded resume files (.pdf, .docx, .txt) into raw text.
Evaluates extraction quality and returns a score alongside the text.
"""
import pdfplumber
import docx

def parse_resume(file_obj) -> tuple[str, float]:
    """
    Accepts a Flask file object, parses the text based on its extension, 
    and calculates a quality score.
    Returns: (text: str, quality_score: float)
    """
    filename = file_obj.filename.lower()
    text = ""
    
    try:
        if filename.endswith(".pdf"):
            with pdfplumber.open(file_obj) as pdf:
                pages_text = []
                for page in pdf.pages:
                    extracted = page.extract_text()
                    if extracted:
                        pages_text.append(extracted)
                text = "\n".join(pages_text)
                
        elif filename.endswith(".docx"):
            doc = docx.Document(file_obj)
            paragraphs_text = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n".join(paragraphs_text)
        else:
            text = file_obj.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"Failed to parse resume: {e}")
        text = ""

    # Calculate quality score
    text_lower = text.lower()
    length = len(text_lower)
    
    if length < 200:
        base_score = 0.0
    elif 200 <= length <= 500:
        base_score = 0.3
    elif 500 < length <= 2000:
        base_score = 0.7
    else:
        base_score = 1.0
        
    keyword_bonus = 0.0
    for kw in ["experience", "education", "skills"]:
        if kw in text_lower:
            keyword_bonus += 0.1
            
    final_score = min(1.0, base_score + keyword_bonus)
    
    return text, final_score
