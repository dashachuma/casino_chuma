from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    balance = db.Column(db.Float, nullable=False, default=20.0)

    def __repr__(self):
        return f'<Player {self.username} - Balance: {self.balance}>'

class CARDS(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    deck_id = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), db.ForeignKey('player.username'), nullable=False)
    card = db.Column(db.String, nullable=False)
    game_datetime = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<Card {self.card} for {self.username} in deck {self.deck_id}>'

class GameResults(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), db.ForeignKey('player.username'), nullable=False)
    player_points = db.Column(db.Integer, nullable=False)
    dealer_points = db.Column(db.Integer, nullable=False)
    result = db.Column(db.String(10), nullable=False)  # win / loss / draw
    balance_after_game = db.Column(db.Float, nullable=False)
    game_datetime = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<GameResult {self.result} for {self.username} on {self.game_datetime}>'