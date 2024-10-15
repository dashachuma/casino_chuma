from app import app, db, Player  # Импортируйте ваше приложение и модели
from flask import jsonify

app.app_context().push()  # Создайте контекст приложения

def check_database():
    players = Player.query.all()  # Получаем всех пользователей в таблице Player
    player_list = [{'username': p.username, 'balance': p.balance} for p in players]

    if player_list:
        print("Существующие игроки:")
        for player in player_list:
            print(f"Имя: {player['username']}, Баланс: {player['balance']}")
    else:
        print("Нет зарегистрированных игроков.")

if __name__ == '__main__':
    check_database()