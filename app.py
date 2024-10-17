from flask import Flask, request, jsonify, send_file
import openai
from gtts import gTTS
import os
import firebase_admin
from firebase_admin import credentials, firestore, db
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Initialize Firebase Admin SDK
firebase_cert_path = os.getenv('FIREBASE_CERT_PATH')
database_url = os.getenv('FIREBASE_DATABASE_URL')

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

# Initialize Flask app
app = Flask(__name__)

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
        print(f"Error fetching user data: {e}")
        return None

# Generate personalized question based on user progress
def generate_personalized_question(user_data):
    first_name = user_data.get('fname', 'User')
    slides_completed = user_data.get('slidesCompleted', False)
    video_watched = user_data.get('videoWatched', False)
    video_progress = user_data.get('videoProgress', 0)

    if slides_completed and not video_watched:
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
        print(f"Error getting GPT answer: {e}")
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
            print(f"Error generating audio: {e}")
            return None
    else:
        return None

# Route to fetch user data and generate personalized question
@app.route('/fetch_user_data', methods=['POST'])
def fetch_user():
    email = request.json.get('email')
    if not email:
        return jsonify({"error": "Email is required"}), 400

    user_data = fetch_user_data_by_email(email)
    if not user_data:
        return jsonify({"error": "User not found"}), 404

    question = generate_personalized_question(user_data)
    return jsonify({"personalized_question": question, "user_data": user_data})

# Route to get GPT answer and generate audio response
@app.route('/get_answer', methods=['POST'])
def get_answer():
    data = request.json
    user_data = data.get('user_data')
    user_input = data.get('question')

    if not user_data or not user_input:
        return jsonify({"error": "User data and question are required"}), 400

    answer = get_gpt_answer(user_input, user_data)
    audio_path = generate_audio_response(answer)

    if not audio_path:
        return jsonify({"error": "Failed to generate audio"}), 500

    return jsonify({"gpt_answer": answer, "audio_url": f"/audio/{os.path.basename(audio_path)}"})

# Route to serve audio files
@app.route('/audio/<filename>', methods=['GET'])
def get_audio(filename):
    file_path = os.path.join(audio_dir, filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    else:
        return jsonify({"error": "Audio file not found"}), 404

# Run the Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
