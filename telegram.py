import requests

api_id = 'your_id'
api_hash = 'your_hash'
token = 'your_token'
baseUrl = f'https://api.telegram.org/bot{token}/'
chatId1 = 'your_chat_id'
chatId2 = 'your_chat_id'
chatId3 = 'your_chat_id'

def sendMessage(text):
    data = {'chat_id': {chatId1}, 'text': {text}}
    requests.post(baseUrl + 'sendMessage', data).json()
    data = {'chat_id': {chatId2}, 'text': {text}}
    requests.post(baseUrl + 'sendMessage', data).json()
    data = {'chat_id': {chatId3}, 'text': {text}}
    requests.post(baseUrl + 'sendMessage', data).json()
    return True