import streamlit as st
import openai
from gtts import gTTS
import os
import firebase_admin
from firebase_admin import credentials, firestore, db
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Initialize Firebase Admin SDK
firebase_cert_path = os.getenv('FIREBASE_ADMIN_SDK_PATH')
database_url = os.getenv('FIREBASE_DATABASE_URL')

# Check if the Firebase app is already initialized
try:
    firebase_admin.get_app()
except ValueError:
    cred = credentials.Certificate(firebase_cert_path)
    firebase_admin.initialize_app(cred, {
        'databaseURL': database_url
    })

# Firestore for user data and Realtime Database for progress tracking
firestore_db = firestore.client()
realtime_db = db.reference()

# OpenAI API Key
openai.api_key = os.getenv('OPENAI_API_KEY')

# Directory to save audio files
audio_dir = os.getenv('AUDIO_DIR')
os.makedirs(audio_dir, exist_ok=True)

# Fetch user data from Firestore and Realtime Database using email
def fetch_user_data_by_email(email):
    try:
        users_ref = firestore_db.collection('users')
        query = users_ref.where('email', '==', email).stream()

        user_data = None
        for doc in query:
            user_data = doc.to_dict()
            user_id = doc.id

        if user_data:
            progress_data = realtime_db.child('users').child(user_id).get()
            return {**user_data, **progress_data} if progress_data else user_data
        else:
            return None

    except Exception as e:
        st.error(f"Error fetching user data: {e}")
        return None

# Generate personalized question based on user progress
# Generate personalized question based on user progress
def generate_personalized_question(user_data):
    first_name = user_data.get('fname', 'User')
    slides_completed = user_data.get('slidesCompleted', False)
    video_watched = user_data.get('videoWatched', False)
    video_progress = user_data.get('videoProgress', 0)

    if slides_completed and video_watched:
        return f"Hello {first_name}, you've completed both the slides and the video. Would you like to complete the simulation now?"
    elif slides_completed and not video_watched:
        return f"Hello {first_name}, you have completed the slides. Tell me the steps to perform breast self-examination."
    elif video_watched:
        return f"Hello {first_name}, you have completed the video. Do you have any questions regarding breast self-examination?"
    elif video_progress > 0:
        return f"Hello {first_name}, you have watched {video_progress}% of the video. Would you like to continue learning or ask any questions?"
    else:
        return f"Hello {first_name}, would you like to start learning about breast self-examination?"


# Get GPT answer based on the user-entered question
def get_gpt_answer(question, user_data):
    context = f"User data: First name: {user_data.get('fname')}, Slides completed: {user_data.get('slidesCompleted')}, Video progress: {user_data.get('videoProgress')}%, Video watched: {user_data.get('videoWatched')}."

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert in health and learning personalization."},
                {"role": "user", "content": context + " " + question}
            ],
            max_tokens=150,
            temperature=0.7,
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        st.error(f"Error getting GPT answer: {e}")
        return "I couldn't fetch an answer. Please try again later."

# Generate an audio response using gTTS (Bengali)
def generate_audio_response(text, filename='response.mp3', lang='bn'):
    file_path = os.path.join(audio_dir, filename)
    if text.strip():
        try:
            tts = gTTS(text=text, lang=lang)
            tts.save(file_path)
            return file_path
        except Exception as e:
            st.error(f"Error generating audio: {e}")
            return None
    else:
        return None

# Streamlit UI
st.title('Personalized Health Assistant')

# Input email to fetch user data
email = st.text_input("Enter your email to fetch data:")

if st.button("Fetch User Data"):
    user_data = fetch_user_data_by_email(email)
    if user_data:
        st.write("User Data:", user_data)
        question = generate_personalized_question(user_data)
        st.write("Personalized Question:", question)
    else:
        st.error("User not found or failed to fetch data.")

# Input to ask question based on user data
user_question = st.text_input("Ask a health-related question:")

if st.button("Get Answer"):
    if user_data and user_question:
        answer = get_gpt_answer(user_question, user_data)
        st.write("GPT Answer:", answer)

        audio_path = generate_audio_response(answer)
        if audio_path:
            audio_file = open(audio_path, 'rb')
            st.audio(audio_file.read(), format='audio/mp3')
            st.download_button("Download Audio", audio_file, file_name="response.mp3")
    else:
        st.error("Please fetch user data and enter a question.")
