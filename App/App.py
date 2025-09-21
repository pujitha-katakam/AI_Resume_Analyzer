import nltk
nltk.download('stopwords')
nltk.download('punkt')
import streamlit as st
import pandas as pd
import base64, random, re, io, time, datetime, requests
import pymysql
from pyresparser import ResumeParser
from pdfminer3.layout import LAParams
from pdfminer3.pdfpage import PDFPage
from pdfminer3.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer3.converter import TextConverter
from streamlit_tags import st_tags
from Courses import ds_course, web_course, android_course, ios_course, uiux_course, resume_videos, interview_videos
from PIL import Image
from streamlit_lottie import st_lottie
import plotly.express as px

# 🎨 Page Configuration with Custom CSS & Background
st.set_page_config(page_title="AI Resume Analyzer", page_icon='📄', layout="wide")

page_bg = f'''
<style>
/* App background & fonts */
.stApp {{
    background-image: linear-gradient(135deg, rgba(28,181,224,0.10), rgba(255,75,43,0.06));
    background-attachment: fixed;
    background-size: cover;
    font-family: 'Segoe UI', sans-serif;
}}
h1,h2,h3,h4,h5,h6 {{
    font-family: 'Poppins', sans-serif;
    margin: 6px 0;
}}

/* Inputs & buttons compact style */
.css-1d391kg, .stTextInput, .stFileUploader, .stSelectbox {{
    border-radius: 10px;
    padding: 6px;
    background-color: rgba(255, 255, 255, 0.88);
    box-shadow: 0px 2px 8px rgba(0,0,0,0.06);
}}
.stButton>button {{
    background: linear-gradient(90deg, #ff416c, #ff4b2b);
    color: white;
    font-weight: 600;
    border-radius: 10px;
    padding: 8px 18px;
    transition: transform .18s ease, box-shadow .18s ease;
}}
.stButton>button:hover {{
    transform: translateY(-3px);
    box-shadow: 0px 8px 20px rgba(0,0,0,0.12);
}}

/* Compact container spacing */
.block-container .element-container {{
    padding-top: 6px;
    padding-bottom: 6px;
}}

/* Fade-in and slide animations */
.fade-in {{
    animation: fadeIn 0.6s ease both;
}}
.slide-up {{
    animation: slideUp 0.6s cubic-bezier(.2,.8,.2,1) both;
}}
@keyframes fadeIn {{
    0% {{opacity: 0; transform: translateY(6px);}}
    100% {{opacity: 1; transform: translateY(0);}}
}}
@keyframes slideUp {{
    0% {{opacity:0; transform: translateY(12px);}}
    100% {{opacity:1; transform: translateY(0);}}
}}

/* Chip styles used for tags */
.chips {{
    display:flex;
    flex-wrap:wrap;
    gap:6px;
    margin-top:6px;
}}
.chip {{
    display:inline-block;
    padding:6px 10px;
    border-radius:16px;
    font-size:13px;
    line-height:18px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    transition: transform .12s ease, box-shadow .12s ease;
    white-space: nowrap;
}}
.chip:hover {{
    transform: translateY(-3px);
    box-shadow: 0 8px 18px rgba(0,0,0,0.10);
}}

/* specific color themes */
.chip-matched {{ background:#e6fff5; color:#007a4d; }}
.chip-missing {{ background:#fff1f0; color:#a00000; }}
.chip-recommend {{ background:#fff8e6; color:#b36b00; }}
.chip-skill {{ background:#eef6ff; color:#0b5ea8; }}

/* make links inside chips not wrap weirdly */
.chip a {{ color: inherit; text-decoration:none; }}

/* reduce iframe/pdf margins */
.reportview-container .main .block-container {{
    padding-top: 10px;
    padding-right: 24px;
    padding-left: 24px;
}}

</style>
'''
st.markdown(page_bg, unsafe_allow_html=True)

# 📄 Helper Functions
def get_csv_download_link(df, filename, text):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode('utf-8')).decode('utf-8')
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'

def pdf_reader(file):
    resource_manager = PDFResourceManager()
    fake_file_handle = io.StringIO()
    converter = TextConverter(resource_manager, fake_file_handle, laparams=LAParams())
    page_interpreter = PDFPageInterpreter(resource_manager, converter)
    with open(file, 'rb') as fh:
        for page in PDFPage.get_pages(fh, caching=True, check_extractable=True):
            page_interpreter.process_page(page)
        text = fake_file_handle.getvalue()
    converter.close()
    fake_file_handle.close()
    return text

def show_pdf(file_path):
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="900" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

def course_recommender(course_list):
    with st.container():
        st.subheader("📚 Courses & Certificates Recommendations")
        no_of_reco = st.slider('Choose Number of Recommendations:', 1, 10, 5)
        random.shuffle(course_list)
        for idx, (c_name, c_link) in enumerate(course_list[:no_of_reco], 1):
            st.markdown(f"🔗 ({idx}) [{c_name}]({c_link})")

def extract_keywords(text):
    text = text.lower()
    words = re.findall(r'\b[a-zA-Z][a-zA-Z]+\b', text)
    stopwords = set(nltk.corpus.stopwords.words('english'))
    keywords = [word for word in words if word not in stopwords and len(word) > 2]
    return list(dict.fromkeys(keywords))  # preserve order-ish and unique

def load_lottie_url(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

def render_chips(items, chip_class='chip-skill'):
    """
    Render compact chips inline as HTML. items: list of strings.
    chip_class: one of chip-matched / chip-missing / chip-recommend / chip-skill
    """
    if not items:
        return st.markdown("<div class='chips'><small style='color:#666;'>No items found</small></div>", unsafe_allow_html=True)

    # sanitize & build spans
    safe_spans = []
    for it in items:
        label = str(it).strip()
        # escape basic html characters
        label = label.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        span = f"<span class='chip {chip_class}'>{label}</span>"
        safe_spans.append(span)
    chips_html = "<div class='chips slide-up'>" + "".join(safe_spans) + "</div>"
    st.markdown(chips_html, unsafe_allow_html=True)

# =========================
# Database Connection
# =========================
connection = pymysql.connect(host='localhost', user='root', password='2005', db='cv')
cursor = connection.cursor()

def insert_feedback(*args):
    table = 'user_feedback'
    cursor.execute(f"INSERT INTO {table} VALUES (0," + ','.join(['%s']*5) + ")", args)
    connection.commit()

# =========================
# Main Function
# =========================
def run():
    st.markdown(
        """
        <h1 style='text-align:center; font-size: 50px;' class="fade-in">
            <span style='background: linear-gradient(90deg, #ff416c, #ff4b2b); -webkit-background-clip: text; color: transparent;'>Resume</span>
            <span style='background: linear-gradient(90deg, #1cb5e0, #000851); -webkit-background-clip: text; color: transparent;'>Analyzer</span>
        </h1>
        """,
        unsafe_allow_html=True
    )

    st.sidebar.title("⚙️ Navigation")
    activities = ["User", "Feedback", "About", "Admin"]
    choice = st.sidebar.radio("Choose an option:", activities)

    # =========================
    # USER SECTION
    # =========================
    if choice == 'User':
        with st.container():
            st.subheader("🧑‍💻 User Information")
            act_name = st.text_input('👤 Name*')
            act_mail = st.text_input('📧 Email*')
            act_mob  = st.text_input('📱 Mobile Number*')

            pdf_file = st.file_uploader("📂 Upload Your Resume (PDF)", type=["pdf"])
            jd_file = st.file_uploader("📑 Upload Job Description (Optional)", type=["pdf", "txt"])

            jd_text = ""
            if jd_file:
                if jd_file.type == "application/pdf":
                    with open("./Uploaded_Resumes/"+jd_file.name, "wb") as f:
                        f.write(jd_file.getbuffer())
                    jd_text = pdf_reader("./Uploaded_Resumes/"+jd_file.name)
                else:
                    jd_text = jd_file.read().decode("utf-8")

            if pdf_file:
                save_image_path = './Uploaded_Resumes/'+pdf_file.name
                with open(save_image_path, "wb") as f:
                    f.write(pdf_file.getbuffer())
                show_pdf(save_image_path)

                resume_data = ResumeParser(save_image_path).get_extracted_data()
                if resume_data:
                    resume_text = pdf_reader(save_image_path)
                    st.success(f"👋 Hello {resume_data.get('name','Candidate')}")

                    # =========================
                    # Job Description Match
                    # =========================
                    jd_keywords = []
                    if jd_text:
                        st.subheader("📊 Job Description Match")
                        resume_keywords = extract_keywords(resume_text)
                        jd_keywords = extract_keywords(jd_text)
                        matched_keywords = list(set(resume_keywords) & set(jd_keywords))
                        missing_keywords = list(set(jd_keywords) - set(resume_keywords))

                        match_score = int((len(matched_keywords) / len(jd_keywords)) * 100) if jd_keywords else 0
                        # small inline progress bar
                        st.progress(match_score)
                        st.success(f"✅ Match Score: {match_score}%")

                        st.markdown("**Matched Keywords:**")
                        render_chips(matched_keywords, chip_class='chip-matched')

                        st.markdown("**Missing Keywords:**")
                        render_chips(missing_keywords, chip_class='chip-missing')

                    # =========================
                    # Skills Extracted
                    # =========================
                    st.subheader("🛠 Skills Extracted")
                    # show extracted skills as chips
                    skills = resume_data.get('skills', []) or []
                    render_chips(skills, chip_class='chip-skill')

                    st.subheader("✨ Recommended Skills")
                    recommended_skills = [skill for skill in jd_keywords if skill not in skills] if jd_keywords else []
                    if recommended_skills:
                        render_chips(recommended_skills, chip_class='chip-recommend')
                    else:
                        st.info("✅ Your resume covers almost all JD skills!" if jd_keywords else "Upload a Job Description for recommendations.")

                    # =========================
                    # Resume Key Sections Analysis
                    # =========================
                    resume_score = 0
                    st.subheader("📈 Resume Key Sections Analysis")

                    # Objective/Summary
                    if 'objective' in resume_text.lower() or 'summary' in resume_text.lower():
                        resume_score += 6
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added Objective/Summary</h5>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h5 style='text-align: left; color: #000000;'>[-] Please add your career objective.</h5>", unsafe_allow_html=True)

                    # Education
                    if any(x in resume_text.lower() for x in ['education','school','college']):
                        resume_score += 12
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added Education Details</h5>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h5 style='text-align: left; color: #000000;'>[-] Please add Education.</h5>", unsafe_allow_html=True)

                    # Experience
                    if 'experience' in resume_text.lower():
                        resume_score += 16
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added Experience</h5>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h5 style='text-align: left; color: #000000;'>[-] Please add Experience.</h5>", unsafe_allow_html=True)

                    # Internships
                    if any(x in resume_text.lower() for x in ['internships','internship']):
                        resume_score += 6
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added Internships</h5>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h5 style='text-align: left; color: #000000;'>[-] Please add Internships.</h5>", unsafe_allow_html=True)

                    # Skills Section
                    if any(x in resume_text.lower() for x in ['skills','skill']):
                        resume_score += 7
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added Skills</h5>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h5 style='text-align: left; color: #000000;'>[-] Please add Skills.</h5>", unsafe_allow_html=True)

                    # Hobbies
                    if 'hobbies' in resume_text.lower():
                        resume_score += 4
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added your Hobbies</h5>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h5 style='text-align: left; color: #000000;'>[-] Please add Hobbies.</h5>", unsafe_allow_html=True)

                    # Interests
                    if 'interests' in resume_text.lower():
                        resume_score += 5
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added your Interests</h5>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h5 style='text-align: left; color: #000000;'>[-] Please add Interests.</h5>", unsafe_allow_html=True)

                    # Achievements
                    if 'achievements' in resume_text.lower():
                        resume_score += 13
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added your Achievements</h5>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h5 style='text-align: left; color: #000000;'>[-] Please add Achievements.</h5>", unsafe_allow_html=True)

                    # Certifications
                    if any(x in resume_text.lower() for x in ['certifications','certification']):
                        resume_score += 12
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added your Certifications</h5>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h5 style='text-align: left; color: #000000;'>[-] Please add Certifications.</h5>", unsafe_allow_html=True)

                    # Projects
                    if any(x in resume_text.lower() for x in ['projects','project']):
                        resume_score += 19
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added your Projects</h5>", unsafe_allow_html=True)
                    else:
                        st.markdown("<h5 style='text-align: left; color: #000000;'>[-] Please add Projects.</h5>", unsafe_allow_html=True)

                    # Final Resume Score
                    st.subheader(f"🏆 Total Resume Score: {resume_score}/100")
                    

                    # =========================
                    # Recommendations & Videos (2-column row-wise medium size)
                    # =========================
                    course_recommender(ds_course)
                    st.subheader("🎥 Helpful Videos")

                    # Two medium-size videos side-by-side
                    col1, col2 = st.columns(2)
                    with col1:
                        # You can control a little the height by passing a url; otherwise Streamlit sizes it responsively
                        v1 = random.choice(resume_videos)
                        st.markdown("<div style='max-width:100%;'><p style='margin:4px 0 8px 0;font-weight:600;'>Resume Tips</p></div>", unsafe_allow_html=True)
                        st.video(v1, start_time=0)

                    with col2:
                        v2 = random.choice(interview_videos)
                        st.markdown("<div style='max-width:100%;'><p style='margin:4px 0 8px 0;font-weight:600;'>Interview Tips</p></div>", unsafe_allow_html=True)
                        st.video(v2, start_time=0)
                    if pdf_file and jd_file:
                        st.balloons()   # 🎈 Balloons floating 

                    
                else:
                        st.error("❌ Could not process the resume. Please try again!")

    # =========================
    # FEEDBACK SECTION
    # =========================
    elif choice == "Feedback":
        st.header("📝 Give Feedback")
        lottie_feedback = load_lottie_url("https://assets7.lottiefiles.com/packages/lf20_jbrw3hcz.json")
        st_lottie(lottie_feedback, height=120, key="feedback_lottie")
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        with st.form("feedback_form"):
            feed_name = st.text_input("Name")
            feed_email = st.text_input("Email")
            feed_score = st.slider("Rate Us 1-5", 1, 5)
            comments = st.text_input("Comments")
            submitted = st.form_submit_button("Submit")
            if submitted:
                insert_feedback(feed_name, feed_email, feed_score, comments, ts)
                st.success("Thanks for your feedback! 🎉")
                # small confetti Lottie for feedback too
                l2 = load_lottie_url("https://assets2.lottiefiles.com/packages/lf20_jbrw3q3k.json")
                if l2:
                    st_lottie(l2, height=120, key="fb_celebrate")

        plotfeed_data = pd.read_sql('SELECT * FROM user_feedback', connection)
        if not plotfeed_data.empty:
            st.subheader("User Ratings")
            fig = px.pie(plotfeed_data, names='feed_score', title="User Rating Distribution")
            st.plotly_chart(fig)
            st.subheader("User Comments")
            st.dataframe(plotfeed_data[['feed_name','comments']])

    # =========================
       # ABOUT SECTION
    # =========================
    elif choice == "About":
        st.header("🤖 About AI Resume Analyzer")
        st.markdown(
            """
            <p style='font-size:18px;'>
            The <b>AI Resume Analyzer</b> is an intelligent tool that parses your resume using NLP, 
            analyzes your skills, predicts your job field, and recommends courses, skills, and improvements.
            </p>
            """, unsafe_allow_html=True
        )

        # Feature

        
        # Feature Cards
        with st.container():
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(
                    """
                    <div style="background: linear-gradient(135deg,#ff416c,#ff4b2b);
                                padding: 20px; border-radius: 15px; text-align:center; color:white;">
                        <h3>📄 Resume Analysis</h3>
                        <p>Upload your resume and get instant skill extraction, experience summary, and level prediction.</p>
                    </div>
                    """, unsafe_allow_html=True
                )
            with col2:
                st.markdown(
                    """
                    <div style="background: linear-gradient(135deg,#1cb5e0,#000851);
                                padding: 20px; border-radius: 15px; text-align:center; color:white;">
                        <h3>🎯 Job Matching</h3>
                        <p>Compare your resume with job descriptions and get match scores and missing skill suggestions.</p>
                    </div>
                    """, unsafe_allow_html=True
                )
            with col3:
                st.markdown(
                    """
                    <div style="background: linear-gradient(135deg,#ffb347,#ffcc33);
                                padding: 20px; border-radius: 15px; text-align:center; color:white;">
                        <h3>📚Recommendations</h3>
                        <p>Receive course, skill, and video recommendations to improve your profile and interview readiness.</p>
                    </div>
                    """, unsafe_allow_html=True
                )
        
        st.markdown("---")
        
        # How to use
        st.subheader("💡 How to Use")
        st.markdown("""
        1. Go to the *User* section and upload your resume (PDF).  
        2. Optionally, upload a *Job Description* to check your match.  
        3. View your *skills, recommendations, and course suggestions*.  
        4. Give feedback in the *Feedback* section.  
        5. Admins can check all users and feedback in the *Admin* section.
        """)

    # =========================
    # ADMIN SECTION
    # =========================
    elif choice == "Admin":
        st.header("🔒 Admin Login")
        ad_user = st.text_input("Username")
        ad_pass = st.text_input("Password", type='password')
        if st.button("Login"):
            if ad_user=="admin" and ad_pass=="admin@resume-analyzer":
                st.success("Welcome Admin! 🎉")
                with st.spinner("Fetching data..."):
                    time.sleep(1.2)
                df_users = pd.read_sql('SELECT * FROM user_data', connection)
                df_feedback = pd.read_sql('SELECT * FROM user_feedback', connection)
                st.subheader("Users Data")
                st.dataframe(df_users)
                st.markdown(get_csv_download_link(df_users,"User_Data.csv","Download Users Report"), unsafe_allow_html=True)
                st.subheader("Feedback Data")
                st.dataframe(df_feedback)
            else:
                st.error("❌ Wrong credentials!")

run()
