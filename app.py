from flask import Flask, render_template, url_for, jsonify, request, session
from flask_session import Session
import requests
import json

app = Flask(__name__)

app.config['SECRET_KEY'] = 'your_secret_key' #зачем-то надо секретный ключ придумать


app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_THRESHOLD'] = 500
Session(app)

@app.route('/generate_deck', methods=['GET'])
def generate_deck():
    response = requests.get('https://deckofcardsapi.com/api/deck/new/shuffle/?deck_count=1')
    deck = response.json()
    deck_id = deck['deck_id']

    session['deck_id'] = deck_id  

    draw_response = requests.get(f'https://deckofcardsapi.com/api/deck/{deck_id}/draw/?count=2')
    cards = draw_response.json()['cards']
    session['cards'] = cards  

    points = calculate_points(cards)
    return render_template('new_page.html', cards=cards, points=points, deck_id=deck_id)

@app.route('/stop_cards', methods=['POST'])
def stop_cards():
    deck_id = session.get('deck_id')
    
	dealer_cards = session.get('dealer_cards', [])

    draw_dealer = requests.get(f'https://deckofcardsapi.com/api/deck/{deck_id}/draw/?count=1')
    new_card = draw_dealer.json().get('cards', [])
    dealer_cards.append(new_card[0])

    session['dealer_cards'] = dealer_cards  

    
    return render_template('new_page.html', card=cards, dealer_cards=dealer_cards, deck_id=deck_id)

@app.route('/reset_game', methods=['GET'])
def reset_game():
    session.pop('deck_id', None) 
    session.pop('cards', None)    
    return render_template('index.html')
	
@app.route('/draw_card', methods=['POST', 'GET'])
def draw_card():
    deck_id = session.get('deck_id')
    cards = session.get('cards', [])

    draw_response = requests.get(f'https://deckofcardsapi.com/api/deck/{deck_id}/draw/?count=1')
    new_card = draw_response.json()['cards'][0]
    cards.append(new_card)

    session['cards'] = cards  

    points = calculate_points(cards)
    return render_template('new_page.html', deck_id=deck_id, cards=cards, points=points)

def calculate_points(cards):
    points = 0
    ace_count = 0

    for card in cards:
        value = card['value']

        if value in ['2', '3', '4', '5', '6', '7', '8', '9', '10']:
            points += int(value)
        elif value == 'ACE':
            ace_count += 1
            points += 11
        else:
            points += 10

    while points > 21 and ace_count > 0:
        points -= 10
        ace_count -= 1

    return points

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/new_page')
def new_page():
    cards = session.get('cards', [])
    points = calculate_points(cards)
    deck_id = session.get('deck_id')
    return render_template('new_page.html', cards=cards, points=points, deck_id=deck_id)

if __name__ == '__main__':
    app.run(debug=True)

#test
