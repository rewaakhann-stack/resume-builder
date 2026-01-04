import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
import qrcode
import tempfile
import os
from supabase import create_client, Client

# --- 1. CONFIGURATION & SETUP ---
st.set_page_config(page_title="The Opportunity CV", page_icon="🎓", layout="wide")

# --- 2. HELPER FUNCTIONS ---

def clean_text(text):
    """
    Sanitizes text for ATS and PDF compatibility.
    - Removes em-dashes (—) and en-dashes (–) replacing them with hyphens (-).
    - Removes smart quotes.
    - Forces Latin-1 encoding to prevent PDF crashes.
    """
    if not text: return ""
    replacements = {
        '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '-', '\u2022': '-', '…': '...'
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    
    # Final scrub for any remaining non-standard dashes
    text = text.replace("—", "-").replace("–", "-")
    
    return text.encode('latin-1', 'replace').decode('latin-1')

@st.cache_resource
def init_db():
    """Initializes the database connection only once."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        return None

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Intelligence Engine")
    
    if 'GOOGLE_API_KEY' in st.secrets:
        api_key = st.secrets['GOOGLE_API_KEY']
        st.success("✅ Community Key Active")
    else:
        api_key = st.text_input("Google Gemini API Key", type="password", help="Get free key at aistudio.google.com")
        
    st.markdown("---")
    st.info("🔒 Data Privacy: Your resume is processed in memory and not permanently stored.")

# --- 4. MAIN UI ---
st.title("🎓 The Opportunity CV")
st.markdown("### The ATS-Crushing Resume Builder")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Profile")
    user_name = st.text_input("Full Name", placeholder="Jane Doe")
    user_email = st.text_input("Email (Required)", placeholder="jane@example.com")
    contact_info = st.text_input("Contact Info", placeholder="London | +44 7700 900000")
    video_url = st.text_input("Video Pitch Link", placeholder="https://youtube.com/...")
    
    st.markdown("---")
    st.markdown("**Resume Sections**")
    education_text = st.text_area("Education", height=100, placeholder="Harvard University, B.A. Economics (2024)")
    skills_text = st.text_area("Technical Skills", height=80, placeholder="Python, Policy Analysis, Data Visualization")
    awards_text = st.text_area("Awards", height=80, placeholder="Fulbright Scholar, Dean's List")
    volunteering_text = st.text_area("Volunteering / Social Work", height=80, placeholder="Community Organizer, Flood Relief Drive")
    
    st.markdown("**Professional Experience**")
    current_resume = st.text_area("Paste Old Experience Bullets", height=200, help="Paste your raw bullet points here.")

with col2:
    st.subheader("2. Target")
    job_desc = st.text_area("Paste Job Description (for ATS Tailoring)", height=600, help="The AI will extract keywords from this to rewrite your experience.")

# --- 5. LOGIC ENGINE ---
if st.button("✨ Generate Resume", type="primary"):
    if not api_key:
        st.error("⚠️ API Key is missing.")
    elif not current_resume or not job_desc or not user_email:
        st.error("⚠️ Please fill in Email, Resume, and Job Description.")
    else:
        # A. DATABASE LOGGING
        supabase = init_db()
        if supabase:
            try:
                data = {
                    "name": user_name,
                    "email": user_email,
                    "resume_text": current_resume,
                    "job_description": job_desc
                }
                supabase.table("submissions").insert(data).execute()
                print(f"Log: Saved data for {user_email}")
            except Exception as e:
                print(f"DB Log Failed: {e}") 
        
        # B. AI GENERATION (Indeed-Level Prompting)
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-pro')

            with st.spinner("🤖 AI is optimizing for ATS keywords..."):
                prompt = f"""
                You are an expert Resume Writer and ATS Algorithm Specialist. 
                Rewrite the following "Old Experience" to perfectly match the "Target Job".

                TARGET JOB DESCRIPTION:
                {job_desc}

                OLD EXPERIENCE:
                {current_resume}

                STRICT INSTRUCTIONS:
                1. KEYWORD MATCHING: Identify the top 5 hard skills/keywords from the Target Job and ensure they appear naturally in the rewritten bullets.
                2. FORMAT: Use standard bullet points. Start every bullet with a strong Action Verb (e.g., Led, Developed, Analyzed).
                3. METRICS: Wherever possible, imply or include impact (e.g., "resulting in improved efficiency" or "impacting X stakeholders").
                4. TONE: Professional, corporate, and direct.
                5. FORBIDDEN: Do NOT use em-dashes (—). Use only standard hyphens (-). Do NOT use generic buzzwords like "hard worker."
                
                OUTPUT FORMAT:
                Provide ONLY the bullet points. No introductory text. No explanations.
                """
                
                response = model.generate_content(prompt)
                st.session_state['generated_experience'] = response.text
                st.session_state['step'] = 2

        except Exception as e:
            st.error(f"AI Error: {str(e)}")

# --- 6. PDF GENERATION ---
if 'step' in st.session_state and st.session_state['step'] >= 2:
    st.divider()
    st.header("3. Final Polish")
    col_edit, col_preview = st.columns([1, 1])
    
    with col_edit:
        final_exp = st.text_area("Refine Experience", value=st.session_state['generated_experience'], height=400)
    
    with col_preview:
        if st.button("📥 Download PDF"):
            try:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)
                
                # --- PDF BUILDER FUNCTIONS ---
                def add_section(title, body):
                    if body:
                        clean_body = clean_text(body)
                        pdf.set_font("Times", "B", 12)
                        pdf.cell(0, 6, title.upper(), ln=True)
                        # Draw a clean line under the header
                        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                        pdf.ln(2)
                        # Body Text
                        pdf.set_font("Times", "", 10.5) # Standard readable size
                        pdf.multi_cell(0, 5, clean_body)
                        pdf.ln(4) # Space after section

                # 1. HEADER (Name & Contact)
                pdf.set_font("Times", "B", 22)
                pdf.cell(0, 10, clean_text(user_name), ln=True, align="C")
                pdf.set_font("Times", "", 10)
                pdf.cell(0, 5, clean_text(contact_info), ln=True, align="C")
                
                # 2. QR CODE (Optional)
                if video_url:
                    qr = qrcode.QRCode(box_size=10, border=2)
                    qr.add_data(video_url)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                        img.save(tmp_file.name)
                        qr_path = tmp_file.name
                    # Position Top Right
                    pdf.image(qr_path, x=170, y=10, w=22)
                    pdf.set_xy(170, 32)
                    pdf.set_font("Times", "I", 7)
                    pdf.cell(22, 4, "Video Intro", align="C", link=video_url)
                    os.unlink(qr_path)
                
                pdf.ln(8) # Space after header

                # 3. SECTIONS (Order optimized for Freshers/Career Switchers)
                add_section("Education", education_text)
                add_section("Technical Skills", skills_text)
                add_section("Professional Experience", final_exp) # The AI Rewritten part
                add_section("Volunteering & Social Work", volunteering_text)
                add_section("Awards & Grants", awards_text)

                html_pdf = pdf.output(dest="S").encode("latin-1", errors='replace')
                st.download_button(
                    label="Download ATS-Optimized PDF",
                    data=html_pdf,
                    file_name="Resume.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"PDF Error: {str(e)}")
