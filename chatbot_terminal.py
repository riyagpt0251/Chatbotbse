import requests
import json

def ask_chatbot(question):
    url = "http://127.0.0.1:5000/chat"
    headers = {"Content-Type": "application/json"}
    data = {"text": question}
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        response_data = response.json()
        print(f"Chatbot: {response_data.get('response_text')}")
    else:
        print("Failed to get a response from the chatbot.")

if __name__ == "__main__":
    print("Welcome to the Chatbot! Type 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            break
        ask_chatbot(user_input)
