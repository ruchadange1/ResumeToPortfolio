import streamlit as st
import fitz
import re
import os
import json
import zipfile
import random
import time
import qrcode
from io import BytesIO
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

# ---------- Phase 1: Configuration & Setup ----------
st.set_page_config(page_title="Resume2PortfolioAI Pro", page_icon="🧠", layout="wide")

# ---------- Phase 2: Themes & Constants ----------
THEMES = [
    {"name":"Aurora Pro","bg":"#0b1220","card":"rgba(255,255,255,0.06)","text":"#e5e7eb",
     "accent1":"#2563eb","accent2":"#a855f7","accent3":"#ec4899","font_heading":"Poppins","font_body":"Inter"},
    {"name":"Sunset Studio","bg":"#120a0a","card":"rgba(255,255,255,0.08)","text":"#fff7ed",
     "accent1":"#f97316","accent2":"#fb7185","accent3":"#f59e0b","font_heading":"Montserrat","font_body":"Nunito"},
    {"name":"Emerald Glass","bg":"#04120d","card":"rgba(255,255,255,0.07)","text":"#ecfdf5",
     "accent1":"#22c55e","accent2":"#06b6d4","accent3":"#10b981","font_heading":"Space Grotesk","font_body":"DM Sans"},
    {"name":"Mono Minimal","bg":"#070707","card":"rgba(255,255,255,0.07)","text":"#f4f4f5",
     "accent1":"#ffffff","accent2":"#a1a1aa","accent3":"#71717a","font_heading":"IBM Plex Sans","font_body":"IBM Plex Sans"},
    {"name":"Oceanic Depth","bg":"#0f172a","card":"rgba(255,255,255,0.05)","text":"#f1f5f9",
     "accent1":"#38bdf8","accent2":"#818cf8","accent3":"#6366f1","font_heading":"Outfit","font_body":"Roboto"}
]

# ---------- Phase 3: Backend Custom Logic (Unchanged) ----------
def extract_pdf_text(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def find_email(text):
    m = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    return m[0] if m else ""

def find_phone(text):
    m = re.findall(r"(\+?\d[\d -]{8,}\d)", text)
    return m[0] if m else ""

def find_linkedin(text):
    m = re.findall(r"(https?://(www\.)?linkedin\.com/[^\s]+)", text)
    return m[0][0] if m else ""

def find_github(text):
    m = re.findall(r"(https?://(www\.)?github\.com/[^\s]+)", text)
    return m[0][0] if m else ""

def guess_name(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines: return "Your Name"
    c = lines[0]
    if "@" in c or "linkedin" in c.lower() or "github" in c.lower():
        return lines[1] if len(lines)>1 else "Your Name"
    return c[:40]

def extract_skills(text):
    common = ["python","java","c++","c","sql","mysql","mongodb","firebase","machine learning","deep learning","nlp",
              "opencv","tensorflow","pytorch","html","css","javascript","react","node","express","php","flutter",
              "aws","docker","kubernetes","git","github","power bi","tableau"]
    t = text.lower()
    found = [s.title() for s in common if s in t]
    return sorted(list(set(found)))

def extract_education(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    edu=[]
    for l in lines:
        if any(x in l.lower() for x in ["b.tech","btech","diploma","ssc","hsc","university","college","bachelor","master","phd"]):
            edu.append(l)
    return edu[:4] if edu else []

def extract_certifications(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    certs = []
    keywords = ["certified", "certification", "certificate", "licence", "award"]
    for l in lines:
        if any(k in l.lower() for k in keywords):
            if len(l) < 100:
                certs.append(l)
    return certs[:5] if certs else []

def extract_projects(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    lower = text.lower()
    if "project" not in lower: return []
    start=None
    for i,l in enumerate(lines):
        if "project" in l.lower():
            start=i; break
    if start is None: return []
    chunk=lines[start:start+35]
    projects=[]
    for l in chunk:
        if "project" in l.lower(): continue
        if 6 < len(l) < 80 and len(projects)<4:
            projects.append({"name":l,"desc":"Project description extracted from resume.","tech":""})
    return projects

def generate_simple_faq(data):
    """
    Generates a simple FAQ list based on extracted data.
    """
    name = data.get('name', 'The Candidate')
    skills = ", ".join(data.get('skills', [])[:5])
    
    faq = [
        ("What are your top skills?", f"My core technical strengths include {skills}."),
        ("Do you have project experience?", f"Yes! I have worked on projects like '{data.get('projects', [{}])[0].get('name', 'various projects')}'. Check the Projects section for more."),
        ("How can I contact you?", f"You can reach me via email at {data.get('email', 'provided in contact section')}."),
        ("What is your educational background?", f"I studied {data.get('education', ['Computer Science'])[0]}.")
    ]
    return faq

def generate_css(theme):
    return f"""
/* Generated by Resume2PortfolioAI Pro */
:root {{
    --bg-color: {theme['bg']};
    --card-bg: {theme['card']};
    --text-color: {theme['text']};
    --accent-1: {theme['accent1']};
    --accent-2: {theme['accent2']};
    --accent-3: {theme['accent3']};
    --font-heading: '{theme['font_heading']}', sans-serif;
    --font-body: '{theme['font_body']}', sans-serif;
}}
/* ... (Rest of CSS logic is handled in template, simplified here for brevity) ... */
body {{ background-color: var(--bg-color); color: var(--text-color); font-family: var(--font-body); }}
h1, h2, h3 {{ font-family: var(--font-heading); }}
"""

def build_portfolio(output_dir, data, pdf_buffer=None):
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("index.html")
    
    # Add FAQ data for template
    data['faq'] = generate_simple_faq(data)
    
    html = template.render(**data)

    os.makedirs(output_dir, exist_ok=True)

    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    with open(os.path.join(output_dir, "style.css"), "w", encoding="utf-8") as f:
        f.write(generate_css(data["theme"]))

    if pdf_buffer:
        with open(os.path.join(output_dir, "resume.pdf"), "wb") as f:
            f.write(pdf_buffer.getbuffer())

    with open(os.path.join(output_dir, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def zip_folder(folder_path, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, folder_path)
                zf.write(full_path, arcname=rel_path)

def generate_qr_code(url):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img

# ---------- Phase 4: Premium UI Components ----------

def render_custom_css():
    st.markdown("""
    <style>
        /* Main Gradient Background */
        .stApp {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        }
        
        /* Typography & readability fixes */
        h1, h2, h3, h4, h5, h6 { font-family: 'Inter', sans-serif !important; letter-spacing: -0.5px; color: #f8fafc !important; }
        p, li, span, label, .stMarkdown, .stCaption { color: #cbd5e1 !important; }
        .stButton>button { color: white !important; }
        
        /* Hero Section */
        .hero-container {
            padding: 40px;
            border-radius: 24px;
            background: linear-gradient(120deg, #2563eb, #7c3aed);
            color: white;
            text-align: center;
            box-shadow: 0 20px 50px rgba(37, 99, 235, 0.3);
            margin-bottom: 40px;
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .hero-container::before {
            content: '';
            position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 60%);
            animation: rotate 20s linear infinite;
        }
        @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        
        .hero-title { font-size: 3.5rem; font-weight: 800; margin-bottom: 10px; z-index: 1; position: relative; color: white !important; }
        .hero-subtitle { font-size: 1.2rem; opacity: 0.9; margin-bottom: 25px; z-index: 1; position: relative; font-weight: 300; color: #e2e8f0 !important; }
        
        /* Features Chips */
        .chip-container { display: flex; gap: 10px; justify-content: center; z-index: 1; position: relative; flex-wrap: wrap; }
        .chip {
            background: rgba(255,255,255,0.15);
            padding: 5px 15px; border-radius: 20px;
            font-size: 0.85rem; font-weight: 600;
            backdrop-filter: blur(5px);
            border: 1px solid rgba(255,255,255,0.2);
            color: white !important;
        }

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: #0b1121;
            border-right: 1px solid rgba(255,255,255,0.05);
        }
        section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span {
            color: #94a3b8 !important;
        }
        
        /* KPI Cards */
        div[data-testid="stMetricValue"] { font-size: 24px; color: #38bdf8 !important; }
        div[data-testid="stMetricLabel"] { font-size: 14px; color: #94a3b8 !important; }
        .css-1r6slb0 { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 15px; }
        
        /* Buttons */
        .stButton>button {
            border-radius: 12px; font-weight: 600;
            transition: all 0.3s ease;
        }
        .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.2); }
        
        /* Code Blocks */
        .stCodeBlock { border-radius: 12px; overflow: hidden; border: 1px solid #334155; }
        
        /* Footer */
        .sidebar-footer {
            margin-top: 50px; padding: 20px 0;
            text-align: center; color: #64748b !important; font-size: 0.8rem;
            border-top: 1px solid rgba(255,255,255,0.05);
        }
    </style>
    """, unsafe_allow_html=True)

def render_header():
    st.markdown("""
        <div class="hero-container">
            <div class="hero-title">Resume2PortfolioAI <span style="opacity:0.6">Pro</span></div>
            <div class="hero-subtitle">Transform your resume into a premium personal website in seconds using AI.</div>
            <div class="chip-container">
                <span class="chip">✨ AI Powered Extraction</span>
                <span class="chip">🎨 5+ Premium Themes</span>
                <span class="chip">🚀 GitHub Pages Ready</span>
                <span class="chip">� AI Chat Assistant</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    with st.sidebar:
        st.subheader("🛠️ Configuration")
        st.write("") 
        
        st.markdown("Download the guide to optimize your resume for AI.")
        st.download_button("📄 Template Guide", "Make sure your resume is readable!", disabled=True)
        st.divider()

        resume_pdf = st.file_uploader("1️⃣ Upload Resume (PDF)", type=["pdf"], help="Select your standard PDF resume.")
        
        st.write("")
        theme_choice = st.selectbox("2️⃣ Select Theme", ["Random (Auto)"] + [t["name"] for t in THEMES], help="Choose a visual style for your portfolio.")
        
        st.write("")
        role = st.selectbox("3️⃣ Your Role Tagline", 
                           ["AI/ML Developer", "Data Analyst", "Full Stack Developer", "Backend Engineer", 
                            "Frontend Developer", "Cloud/DevOps Engineer", "Software Engineer"],
                           help="This will be the main title of your portfolio.")
        
        st.divider()
        generate_btn = st.button("🚀 Generate Portfolio", type="primary", use_container_width=True, disabled=not resume_pdf)

        st.markdown("""
            <div class="sidebar-footer">
                Resume2PortfolioAI Pro v1.1<br>
                Designed for Developers
            </div>
        """, unsafe_allow_html=True)
        
        return resume_pdf, theme_choice, role, generate_btn

def render_onboarding():
    st.markdown("### 🚦 How it works")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("#### 1. Upload")
        st.caption("Upload your PDF resume.")
    with c2:
        st.markdown("#### 2. Customize")
        st.caption("Pick a premium theme.")
    with c3:
        st.markdown("#### 3. Generate")
        st.caption("AI builds your site.")
    with c4:
        st.markdown("#### 4. Deploy")
        st.caption("Host live on GitHub.")
    
    st.info("👈 Please start by uploading your resume in the sidebar!")

def render_chat_assistant(data, text_content):
    st.write("")
    st.markdown("### 💬 Ask About Me (AI Assistant)")
    st.caption("Ask questions about the candidate based on the uploaded resume.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Quick Actions
    col1, col2, col3, col4 = st.columns(4)
    if col1.button("Best Project?"):
        prompt = "Explain my best project."
    elif col2.button("My Skills?"):
        prompt = "Summarize my top skills."
    elif col3.button("Why Hire Me?"):
        prompt = "What makes me suitable for this role?"
    elif col4.button("Intro"):
        prompt = "Generate a recruiter intro."
    else:
        prompt = None

    if user_input := st.chat_input("Ask a question about this resume...") or prompt:
        if not prompt: prompt = user_input
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Simple Logic-based AI (Keyword Search Fallback)
        response = "I couldn't find specific details in the resume."
        p_lower = prompt.lower()
        
        if "project" in p_lower:
            projs = data.get("projects", [])
            if projs:
                response = f"My best project is likely **{projs[0]['name']}**. Description: {projs[0]['desc']}"
            else:
                response = "I did not find detailed projects in the resume text."
        elif "skill" in p_lower:
            skills = ", ".join(data.get("skills", [])[:10])
            response = f"My top technical skills include: **{skills}**."
        elif "hire" in p_lower or "suitable" in p_lower:
            response = f"I have experience with {', '.join(data.get('skills', [])[:3])} and a background in {data.get('education', ['tech'])[0]}. I am passionate about building software."
        elif "intro" in p_lower:
            response = f"Hi! I am {data['name']}, a {data['title'].split('|')[0]} proficient in {', '.join(data.get('skills', [])[:3])}. I have worked on {len(data['projects'])} key projects."
        else:
            # General Search
            matches = [line for line in text_content.split('\n') if any(word in line.lower() for word in p_lower.split())]
            if matches:
                 response = "Based on the resume: " + matches[0]

        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

def render_dashboard(data, output_dir, zip_path, resume_text):
    st.divider()
    st.markdown("## 📊 Portfolio Dashboard")
    
    # KPI Cards
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🎨 Theme", data['theme']['name'])
    k2.metric("💡 Skills Found", len(data['skills']))
    k3.metric("📂 Projects", len(data['projects']))
    k4.metric("🔗 Links", sum(1 for x in [data['linkedin'], data['github'], data['email']] if x))

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["👁️ Live Preview", "� Ask About Me", "�📝 Extracted Data", "📂 Generated Files", "☁️ Deploy Guide"])

    with tab1:
        st.subheader("Website Preview (index.html)")
        st.caption("This is a raw code preview of the generated HTML structure.")
        try:
            with open(os.path.join(output_dir, "index.html"), "r", encoding="utf-8") as f:
                html_content = f.read()
                preview_lines = "\n".join(html_content.split("\n")[:400])
                st.code(preview_lines, language="html")
        except Exception as e:
            st.error(f"Could not load preview: {e}")

    with tab2:
        render_chat_assistant(data, resume_text)

    with tab3:
        st.subheader("Structured Data Profile")
        st.json(data)
    
    with tab4:
        st.subheader("File Structure")
        files_data = []
        for root, _, files in os.walk(output_dir):
            for file in files:
                full_path = os.path.join(root, file)
                size = os.path.getsize(full_path)
                files_data.append({"File Name": file, "Size (Bytes)": f"{size:,} B", "Type": file.split('.')[-1].upper()})
        
        st.dataframe(files_data, use_container_width=True)

    with tab5:
        st.subheader("🚀 Deploy & Run Guide")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("#### 💻 Run Locally (Instant)")
            st.markdown("""
            1. **Unzip** the downloaded folder.
            2. Double-click **`index.html`** to open it in your browser.
            """)
        
        with c2:
            st.markdown("#### 🌐 Host on GitHub Pages")
            st.markdown("Run these commands in your terminal:")
        
        deploy_script = f"""
git init
git add .
git commit -m "Initial portfolio commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
        """
        st.code(deploy_script, language="bash")
        
        # QR Code Section
        st.divider()
        st.subheader("📌 Portfolio QR Code")
        user_github = data['github'] if "github.com" in data['github'] else "github.com/username"
        repo_url = user_github if "http" in user_github else f"https://{user_github}"
        
        if "github.com" not in data['github']:
             st.warning("⚠️ No GitHub link found in resume. Using placeholder for QR.")
        
        qr_img = generate_qr_code(repo_url)
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        byte_im = buf.getvalue()
        
        col_qr, col_info = st.columns([1, 4])
        with col_qr:
            st.image(byte_im, caption="Scan to visit", width=150)
        with col_info:
            st.success(f"QR Code generated for: {repo_url}")
            st.download_button("⬇️ Download QR Code", byte_im, "portfolio_qr.png", "image/png")
        
    # Verification Checklist & Download
    st.divider()
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown("#### ✅ Verification Checklist")
        st.markdown("- [x] Resume Extracted")
        st.markdown(f"- [x] Applied Theme: **{data['theme']['name']}**")
        st.markdown("- [x] HTML & CSS Generated")
        st.markdown("- [x] ZIP Package Ready")
    
    with c2:
        st.success("Ready for Download!")
        with open(zip_path, "rb") as f:
            st.download_button("📦 Download Final ZIP", f, file_name=f"portfolio_{data['name'].replace(' ', '_').lower()}.zip", mime="application/zip", type="primary", use_container_width=True)

# ---------- Phase 5: Main Orchestration ----------
def main():
    render_custom_css()
    render_header()
    
    resume_pdf, theme_choice, role, generate_click = render_sidebar()

    if generate_click and resume_pdf:
        # Progress UI
        progress_bar = st.progress(0, text="Starting AI engine...")
        
        # Step 1: Extraction
        time.sleep(0.5)
        progress_bar.progress(25, text="📄 Extracting resume data...")
        text = extract_pdf_text(resume_pdf)
        
        # Logic
        theme = random.choice(THEMES) if theme_choice == "Random (Auto)" else [t for t in THEMES if t["name"] == theme_choice][0]
        name = guess_name(text)
        email = find_email(text)
        phone = find_phone(text)
        linkedin = find_linkedin(text)
        github = find_github(text)
        skills = extract_skills(text)
        projects = extract_projects(text)
        education = extract_education(text)
        certifications = extract_certifications(text)
        
        progress_bar.progress(50, text="🧠 Analyzing skills and projects...")
        
        data = {
            "name": name,
            "title": f"{role} | Portfolio",
            "summary": "Professional portfolio generated using Resume2PortfolioAI Pro.",
            "email": email, "phone": phone, "linkedin": linkedin, "github": github,
            "skills": skills if skills else ["Python", "Machine Learning", "SQL", "GitHub"],
            "projects": projects if projects else [{"name":"Portfolio Project","desc":"Generated project.","tech":"Python"}],
            "education": education if education else ["University Degree"],
            "certifications": certifications if certifications else ["Certified Developer"],
            "theme": theme,
            "font_heading": theme["font_heading"].replace(" ", "+"),
            "font_body": theme["font_body"].replace(" ", "+"),
            "has_resume": True
        }
        
        progress_bar.progress(75, text="🎨 Applying premium theme & building HTML...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = f"generated_portfolio_{timestamp}"
        build_portfolio(out_dir, data, resume_pdf)
        
        zip_path = f"{out_dir}.zip"
        zip_folder(out_dir, zip_path)
        
        progress_bar.progress(100, text="✅ Done! Portfolio ready.")
        time.sleep(0.5)
        progress_bar.empty()
        
        # Render Result
        render_dashboard(data, out_dir, zip_path, text)
        
    else:
        render_onboarding()

if __name__ == "__main__":
    main()
