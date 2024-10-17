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
            print("No user found with that email.")
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
            print(f"Audio saved to {file_path}.")
        except Exception as e:
            print(f"Error generating audio: {e}")
    else:
        print("No text to convert to audio.")

# Main function to interact with the user continuously
def main():
    email = input("Enter the user's email: ").strip()

    if not email:
        print("Email is required to fetch data.")
        return

    # Fetch user data from Firebase
    user_data = fetch_user_data_by_email(email)

    if user_data:
        # Chat loop for continuous interaction
        while True:
            # Generate personalized question based on the user's progress
            personalized_question = generate_personalized_question(user_data)
            print(f"Personalized Question: {personalized_question}")
            
            # Get user input for further questions or responses
            user_input = input("Your response or question: ").strip()

            if user_input:
                # Get an answer using GPT based on the user question and progress
                answer = get_gpt_answer(user_input, user_data)
                print(f"GPT Answer (English): {answer}")

                # Generate audio response in Bengali
                generate_audio_response(answer)
                print(f"Bengali audio response generated for: {answer}")

            else:
                print("You didn't enter a response.")

            # Ask if the user wants to continue the conversation
            continue_prompt = input("Do you want to continue the conversation? (yes/no): ").strip().lower()
            if continue_prompt != 'yes':
                break

    else:
        print("User not found or no progress data available.")

if __name__ == '__main__':
    main()
