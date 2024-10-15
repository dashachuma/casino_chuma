from flask import Flask, render_template, url_for, request, session, redirect
from flask_session import Session
import requests
from models import CARDS, GameResults, Player, db
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()

app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_THRESHOLD'] = 500
Session(app)

MIN_BET = 2

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        player_name = request.form.get('new_player_name') or request.form.get('existing_player')

        if player_name:
            player = Player.query.filter_by(username=player_name).first()
            if not player and request.form.get('new_player_name'):
                player = Player(username=player_name, balance=20.0)
                db.session.add(player)
                db.session.commit()

            session['player_name'] = player.username
            clear_session()

            return redirect(url_for('index'))

    player_name = session.get('player_name')
    balance = retrieve_balance(player_name)

    players = Player.query.all()
    return render_template('index.html', player_name=player_name, balance=balance, players=players)

def clear_session():
    session.pop('deck_id', None)
    session.pop('cards', None)
    session.pop('cards_dealer', None)
    session.pop('current_bet', None)

def retrieve_balance(player_name):
    if player_name:
        player = Player.query.filter_by(username=player_name).first()
        if player:
            return player.balance
    return None

@app.route('/set_name', methods=['POST'])
def set_name():
    player_name = request.form.get('player_name')
    if player_name:
        player = Player.query.filter_by(username=player_name).first() or Player(username=player_name, balance=20.0)
        if not player.id:
            db.session.add(player)
            db.session.commit()
        session['player_name'] = player.username
        clear_session()
    return redirect(url_for('index'))

@app.route('/generate_deck', methods=['POST'])
def generate_deck():
    player_name = session.get('player_name', 'Игрок')
    player = Player.query.filter_by(username=player_name).first()
    if not player:
        return redirect(url_for('index'))

    balance = player.balance
    bet = request.form.get('bet', 2)

    if bet == 'all_in':
        bet = balance
    else:
        try:
            bet = int(bet)
        except ValueError:
            bet = MIN_BET

    if bet < MIN_BET or bet > balance:
        bet = MIN_BET

    current_bet = bet
    player.balance -= current_bet
    db.session.commit()
    session['current_bet'] = current_bet

    response = requests.get('https://deckofcardsapi.com/api/deck/new/shuffle/?deck_count=1')
    if response.status_code != 200:
        return "Ошибка при создании колоды", 500
    deck = response.json()
    deck_id = deck['deck_id']
    session['deck_id'] = deck_id

    draw_response = requests.get(f'https://deckofcardsapi.com/api/deck/{deck_id}/draw/?count=2')
    if draw_response.status_code != 200:
        return "Ошибка при раздаче карт", 500
    cards = draw_response.json()['cards']
    session['cards'] = cards

    points = calculate_points(cards)

    return render_template('new_page.html', 
                           cards=cards, points=points, deck_id=deck_id,
                           cards_dealer=None, points_dealer=None, 
                           player_name=player_name,
                           balance=player.balance,
                           current_bet=current_bet)

@app.route('/dealer', methods=['GET']) 
def dealer():
    player_name = session.get('player_name', 'Игрок')
    player = Player.query.filter_by(username=player_name).first()
    if not player:
        return redirect(url_for('index'))

    deck_id = session.get('deck_id')
    if not deck_id:
        return redirect(url_for('index'))

    cards_dealer = session.get('cards_dealer', [])

    while calculate_points(cards_dealer) < 17:
        draw_response_dealer = requests.get(f'https://deckofcardsapi.com/api/deck/{deck_id}/draw/?count=1')
        if draw_response_dealer.status_code != 200:
            break  
        new_card = draw_response_dealer.json()['cards'][0]
        cards_dealer.append(new_card)

    session['cards_dealer'] = cards_dealer
    points_dealer = calculate_points(cards_dealer)

    points_player = calculate_points(session.get('cards', []))
    current_bet = session.get('current_bet', 0)
    balance = player.balance

    if points_player > 21:
        result = 'loss'
    elif points_dealer > 21 or points_player > points_dealer:
        result = 'win'
    elif points_player < points_dealer:
        result = 'loss'
    else:
        result = 'draw'

    if result == 'win':
        balance += current_bet * 2
    elif result == 'draw':
        balance += current_bet
    player.balance = balance
    db.session.commit()

    game_result = GameResults(
        username=player_name,
        player_points=points_player,
        dealer_points=points_dealer,
        result=result,
        balance_after_game=balance
    )
    db.session.add(game_result)
    db.session.commit()

    return render_template('new_page.html', 
                           cards=session.get('cards'),
                           points=points_player, 
                           deck_id=deck_id,
                           cards_dealer=cards_dealer, 
                           points_dealer=points_dealer, 
                           player_name=player_name,
                           balance=balance,
                           result=result,
                           current_bet=current_bet)

@app.route('/new_page', methods=['GET'])
def new_page():
    player_name = session.get('player_name', 'Игрок')  
    player = Player.query.filter_by(username=player_name).first()
    if not player:
        return redirect(url_for('index'))

    balance = player.balance  
    cards = session.get('cards', [])
    points = calculate_points(cards)
    deck_id = session.get('deck_id')
    cards_dealer = session.get('cards_dealer')
    points_dealer = calculate_points(cards_dealer) if cards_dealer else None  
    current_bet = session.get('current_bet', None)  

    return render_template('new_page.html', 
                           cards=cards, 
                           points=points, 
                           deck_id=deck_id,
                           cards_dealer=cards_dealer, 
                           points_dealer=points_dealer, 
                           player_name=player_name,
                           balance=balance,
                           current_bet=current_bet)

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

@app.route('/draw_card', methods=['POST'])
def draw_card():
    player_name = session.get('player_name', 'Игрок')
    player = Player.query.filter_by(username=player_name).first()
    if not player:
        return redirect(url_for('index'))

    deck_id = session.get('deck_id')
    if not deck_id:
        return redirect(url_for('index'))

    current_bet = session.get('current_bet', 0)
    cards = session.get('cards', [])

    draw_response = requests.get(f'https://deckofcardsapi.com/api/deck/{deck_id}/draw/?count=1')
    if draw_response.status_code != 200:
        return "Ошибка при вытягивании карты", 500

    new_card = draw_response.json()['cards'][0]
    cards.append(new_card)
    session['cards'] = cards
    points = calculate_points(cards)

    if points > 21:
        result = 'loss'
        balance = player.balance
        player.balance = balance  
        db.session.commit()

        game_result = GameResults(
            username=player_name,
            player_points=points,
            dealer_points=0,
            result=result,
            balance_after_game=balance
        )
        db.session.add(game_result)
        db.session.commit()

        return render_template('new_page.html',
                               cards=cards,
                               points=points,
                               deck_id=deck_id,
                               cards_dealer=None,
                               points_dealer=None,
                               player_name=player_name,
                               balance=balance,
                               result=result,
                               current_bet=current_bet)

    return render_template('new_page.html',
                           cards=cards,
                           points=points,
                           deck_id=deck_id,
                           cards_dealer=session.get('cards_dealer'),
                           points_dealer=calculate_points(session.get('cards_dealer')) if session.get('cards_dealer') else None,
                           player_name=player_name,
                           balance=player.balance,
                           current_bet=current_bet)

@app.route('/reset_game', methods=['GET'])
def reset_game():
    clear_session()
    return redirect(url_for('new_page'))

@app.route('/final_page', methods=['GET'])
def final_page():
    player_name = session.get('player_name', None)
    if not player_name:
        return redirect(url_for('index'))

    game_results = GameResults.query.filter_by(username=player_name).order_by(GameResults.game_datetime.desc()).all()

    if not game_results:
        return render_template('final_page.html', message="Нет данных о последних играх.")

    return render_template('final_page.html', games=game_results)

if __name__ == '__main__':
    app.run(debug=True)