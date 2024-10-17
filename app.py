# Импорт необходимых библиотек и модулей
from flask import Flask, render_template, url_for, request, session, redirect  # Основные функции Flask
from flask_session import Session  # Для работы с сессиями пользователя
import requests  # Для отправки HTTP-запросов к внешним сервисам
from models import CARDS, GameResults, Player, db  # Импорт моделей данных из файла models.py
from flask_sqlalchemy import SQLAlchemy  # Для работы с базой данных

# Создание экземпляра Flask-приложения
app = Flask(__name__)

# Настройка подключения к базе данных SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'  # Указывает, что будем использовать базу данных SQLite в файле app.db
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Отключаем ненужные проверки для улучшения производительности

# Подключение базы данных к приложению Flask
db.init_app(app)

# Создание всех таблиц в базе данных, если они еще не существуют
with app.app_context():
    db.create_all()

# Настройка сессий пользователя
app.config['SECRET_KEY'] = 'your_secret_key'  # Секретный ключ для защиты данных сессии
app.config['SESSION_TYPE'] = 'filesystem'     # Хранение данных сессии на сервере в файловой системе
app.config['SESSION_FILE_THRESHOLD'] = 500    # Максимальное количество файлов сессий перед их очисткой
Session(app)  # Инициализация работы сессий

# Минимальная ставка в игре
MIN_BET = 2

# Главная страница приложения, поддерживает как просмотр (GET), так и отправку данных (POST)
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Получаем имя нового игрока или выбираем существующего
        player_name = request.form.get('new_player_name') or request.form.get('existing_player')

        if player_name:
            # Ищем игрока в базе данных по имени
            player = Player.query.filter_by(username=player_name).first()
            # Если игрока нет и введено новое имя, создаем нового игрока с балансом 20
            if not player and request.form.get('new_player_name'):
                player = Player(username=player_name, balance=20)
                db.session.add(player)
                db.session.commit()

            # Сохраняем имя игрока в сессии
            session['player_name'] = player.username
            clear_session()  # Очищаем другие данные сессии

            
            

    # Получаем имя игрока из сессии
    player_name = session.get('player_name')
    # Получаем текущий баланс игрока
    balance = retrieve_balance(player_name)

    # Получаем список всех игроков из базы данных
    players = Player.query.all()
    # Отображаем главную страницу с информацией о игроке и списком игроков
    return render_template('index.html', player_name=player_name, balance=balance, players=players)

def clear_session():
    """
    Очищает определенные данные из сессии.
    Это нужно, чтобы начать новую игру без старых данных.
    """
    session.pop('deck_id', None)
    session.pop('cards', None)
    session.pop('cards_dealer', None)
    session.pop('current_bet', None)
    session.pop('points', None)
    session.pop('points_dealer', None)
    session.pop('result', None)
    session.pop('dealer_acted', None)  

def retrieve_balance(player_name):
    """
    Возвращает баланс игрока по его имени.
    Если игрок не найден, возвращает None.
    """
    if player_name:
        player = Player.query.filter_by(username=player_name).first()
        if player:
            return player.balance
    return None

# Маршрут для установки имени игрока через форму
@app.route('/set_name', methods=['POST'])
def set_name():
    player_name = request.form.get('player_name')
    if player_name:
        # Ищем игрока по имени или создаем нового с начальным балансом 20
        player = Player.query.filter_by(username=player_name).first() or Player(username=player_name, balance=20)
        if not player.id:
            db.session.add(player)
            db.session.commit()
        # Сохраняем имя игрока в сессии
        session['player_name'] = player.username
        clear_session()  # Очищаем старые данные сессии

    # Перенаправляем на главную страницу
    return redirect(url_for('index'))

# Маршрут для начала новой игры и создания колоды карт
@app.route('/generate_deck', methods=['POST'])
def generate_deck():
    player_name = session.get('player_name', 'Игрок')  # Получаем имя игрока из сессии или ставим "Игрок"
    player = Player.query.filter_by(username=player_name).first()
    if not player:
        return redirect(url_for('index'))

    balance = player.balance
    bet = request.form.get('bet', 2)  # Получаем ставку из формы, по умолчанию 2

    if bet == 'all_in':
        bet = balance  # Если выбрали "всё или ничего", ставка равна всему балансу
    else:
        try:
            bet = int(bet)  # Преобразуем ставку в число
        except ValueError:
            bet = MIN_BET  # Если введено не число, ставим минимальную ставку

    # Проверяем, что ставка не меньше минимальной и не больше баланса
    if bet < MIN_BET or bet > balance:
        bet = MIN_BET

    current_bet = bet
    player.balance -= current_bet  # Вычитаем ставку из баланса игрока
    db.session.commit()
    session['current_bet'] = current_bet  # Сохраняем текущую ставку в сессии

    # Создаем новую колоду карт через внешний сервис
    response = requests.get('https://deckofcardsapi.com/api/deck/new/shuffle/?deck_count=1')
    if response.status_code != 200:
        return "Ошибка при создании колоды", 500
    deck = response.json()
    deck_id = deck['deck_id']
    session['deck_id'] = deck_id  # Сохраняем идентификатор колоды в сессии

    # Раздаем две карты игроку
    draw_response = requests.get(f'https://deckofcardsapi.com/api/deck/{deck_id}/draw/?count=2')
    if draw_response.status_code != 200:
        return "Ошибка при раздаче карт", 500
    cards = draw_response.json().get('cards', [])
    session['cards'] = cards  # Сохраняем карты игрока в сессии

    # Инициализируем данные для дилера
    session['cards_dealer'] = []
    session['dealer_acted'] = False  

    points = calculate_points(cards)  # Считаем очки игрока

    # Показываем новую страницу игры с текущими данными
    return render_template('new_page.html', 
                           cards=cards, 
                           points=points, 
                           deck_id=deck_id,
                           cards_dealer=[],          
                           points_dealer=None, 
                           player_name=player_name,
                           balance=player.balance,
                           current_bet=current_bet,
                           dealer_acted=False)       

# Маршрут для действий дилера после хода игрока
@app.route('/dealer', methods=['GET']) 
def dealer():
    player_name = session.get('player_name', 'Игрок')  # Получаем имя игрока из сессии или ставим "Игрок"
    player = Player.query.filter_by(username=player_name).first()
    if not player:
        return redirect(url_for('index'))

    deck_id = session.get('deck_id')  # Получаем идентификатор колоды из сессии
    if not deck_id:
        return redirect(url_for('index'))

    cards_dealer = session.get('cards_dealer', [])  # Получаем текущие карты дилера из сессии

    # Дилер берет карты, пока сумма очков меньше 17
    while calculate_points(cards_dealer) < 17:
        draw_response_dealer = requests.get(f'https://deckofcardsapi.com/api/deck/{deck_id}/draw/?count=1')
        if draw_response_dealer.status_code != 200:
            break  # Если не получилось взять карту, прекращаем
        new_card = draw_response_dealer.json().get('cards', [])[0]
        cards_dealer.append(new_card)  # Добавляем новую карту к дилеру

    session['cards_dealer'] = cards_dealer  # Сохраняем обновленные карты дилера в сессии
    points_dealer = calculate_points(cards_dealer)  # Считаем очки дилера

    points_player = calculate_points(session.get('cards', []))  # Считаем очки игрока
    current_bet = session.get('current_bet', 0)               # Получаем текущую ставку из сессии
    balance = player.balance                                   # Получаем текущий баланс игрока

    # Определяем результат игры
    if points_player > 21:
        result = 'loss'  # Игрок проигрывает, если очков больше 21
    elif points_dealer > 21 or points_player > points_dealer:
        result = 'win'   # Игрок выигрывает, если у дилера больше 21 или у игрока больше очков
    elif points_player < points_dealer:
        result = 'loss'  # Игрок проигрывает, если у дилера больше очков
    else:
        result = 'draw'  # Ничья, если очки равны

    # Обновляем баланс игрока в зависимости от результата
    if result == 'win':
        balance += current_bet * 2  # Выигрыш удваивает ставку
    elif result == 'draw':
        balance += current_bet      # В случае ничьи возвращаем ставку
    player.balance = balance          # Обновляем баланс игрока
    db.session.commit()               # Сохраняем изменения в базе данных

    # Записываем результат игры в базу данных
    game_result = GameResults(
        username=player_name,
        player_points=points_player,
        dealer_points=points_dealer,
        result=result,
        balance_after_game=balance
    )
    db.session.add(game_result)  # Добавляем запись о результате игры
    db.session.commit()          # Сохраняем изменения

    session['dealer_acted'] = True  # Устанавливаем флаг, что дилер закончил ход

    # Показываем страницу с результатами игры
    return render_template('new_page.html', 
                           cards=session.get('cards', []),
                           points=points_player, 
                           deck_id=deck_id,
                           cards_dealer=cards_dealer, 
                           points_dealer=points_dealer, 
                           player_name=player_name,
                           balance=balance,
                           result=result,
                           current_bet=current_bet,
                           dealer_acted=True)

# Маршрут для отображения текущей страницы игры
@app.route('/new_page', methods=['GET'])
def new_page():
    player_name = session.get('player_name', 'Игрок')  # Получаем имя игрока из сессии или ставим "Игрок"
    player = Player.query.filter_by(username=player_name).first()
    if not player:
        return redirect(url_for('index'))

    balance = player.balance              # Текущий баланс игрока
    cards = session.get('cards', [])      # Карты игрока из сессии
    points = calculate_points(cards)      # Считаем очки игрока
    deck_id = session.get('deck_id')      # Идентификатор колоды
    cards_dealer = session.get('cards_dealer', [])  # Карты дилера из сессии
    points_dealer = calculate_points(cards_dealer) if cards_dealer else None  # Считаем очки дилера, если есть карты
    current_bet = session.get('current_bet', None)    # Текущая ставка
    dealer_acted = session.get('dealer_acted', False) # Был ли ход дилера

    # Показываем страницу игры с текущими данными
    return render_template('new_page.html', 
                           cards=cards, 
                           points=points, 
                           deck_id=deck_id,
                           cards_dealer=cards_dealer,      
                           points_dealer=points_dealer, 
                           player_name=player_name,
                           balance=balance,
                           current_bet=current_bet,
                           dealer_acted=dealer_acted)

def calculate_points(cards):
    """
    Считает количество очков у игрока или дилера.
    - Цифровые карты добавляют столько очков, сколько написано на карте.
    - Валет, Дама, Король дают по 10 очков.
    - Туз дает 11 очков, но если сумма больше 21, то туз считается как 1.
    """
    points = 0         # Общая сумма очков
    ace_count = 0     # Количество тузов

    for card in cards:
        value = card['value']  # Получаем значение карты

        if value in ['2', '3', '4', '5', '6', '7', '8', '9', '10']:
            points += int(value)  # Добавляем номинал карты к очкам
        elif value == 'ACE':
            ace_count += 1        # Увеличиваем счетчик тузов
            points += 11          # Добавляем 11 очков за туз
        else:
            points += 10          # Добавляем 10 очков за Валута, Даму или Короля

    # Если сумма очков больше 21 и есть туз, то уменьшаем очки на 10
    while points > 21 and ace_count > 0:
        points -= 10         # Туз теперь считается как 1 вместо 11
        ace_count -= 1       # Уменьшаем счетчик тузов

    return points  # Возвращаем итоговую сумму очков

# Маршрут для вытягивания новой карты игроком
@app.route('/draw_card', methods=['POST'])
def draw_card():
    player_name = session.get('player_name', 'Игрок')  # Получаем имя игрока или ставим "Игрок"
    player = Player.query.filter_by(username=player_name).first()
    if not player:
        return redirect(url_for('index'))

    deck_id = session.get('deck_id')  # Получаем идентификатор колоды
    if not deck_id:
        return redirect(url_for('index'))

    current_bet = session.get('current_bet', 0)  # Текущая ставка
    cards = session.get('cards', [])              # Текущие карты игрока

    # Берем одну карту из колоды через внешний сервис
    draw_response = requests.get(f'https://deckofcardsapi.com/api/deck/{deck_id}/draw/?count=1')
    if draw_response.status_code != 200:
        return "Ошибка при вытягивании карты", 500

    new_card = draw_response.json().get('cards', [])[0]  # Получаем новую карту из ответа
    cards.append(new_card)          # Добавляем карту к списку игрока
    session['cards'] = cards        # Обновляем карты игрока в сессии
    points = calculate_points(cards) # Считаем новые очки игрока

    if points > 21:
        # Если очков больше 21, игрок проигрывает
        result = 'loss'
        balance = player.balance
        player.balance = balance  # Баланс остается без изменений
        db.session.commit()       # Сохраняем изменения

        # Создаем запись о проигрыше в базе данных
        game_result = GameResults(
            username=player_name,
            player_points=points,
            dealer_points=0,        # Дилер не набрал очков
            result=result,
            balance_after_game=balance
        )
        db.session.add(game_result)  # Добавляем запись
        db.session.commit()          # Сохраняем изменения

        session['dealer_acted'] = False  # Сбрасываем флаг действий дилера

        # Показываем страницу игры с результатом проигрыша
        return render_template('new_page.html',
                               cards=cards,
                               points=points,
                               deck_id=deck_id,
                               cards_dealer=[],          
                               points_dealer=None,
                               player_name=player_name,
                               balance=balance,
                               result=result,
                               current_bet=current_bet,
                               dealer_acted=False)       
    else:
        # Если очков не больше 21, продолжаем игру
        dealer_acted = session.get('dealer_acted', False)
        # Показываем страницу игры с обновленными данными
        return render_template('new_page.html',
                               cards=cards,
                               points=points,
                               deck_id=deck_id,
                               cards_dealer=session.get('cards_dealer', []),    
                               points_dealer=calculate_points(session.get('cards_dealer', [])) if session.get('cards_dealer') else None,
                               player_name=player_name,
                               balance=player.balance,
                               current_bet=current_bet,
                               dealer_acted=dealer_acted)

# Маршрут для сброса текущей игры и очистки данных
@app.route('/reset_game', methods=['GET'])
def reset_game():
    clear_session()  # Очищаем данные сессии
    return redirect(url_for('new_page'))  # Перенаправляем на страницу игры для начала новой

# Маршрут для отображения финальной страницы с историей игр
@app.route('/final_page', methods=['GET'])
def final_page():
    player_name = session.get('player_name', None)  # Получаем имя игрока из сессии
    if not player_name:
        return redirect(url_for('index'))

    # Получаем все результаты игр игрока из базы данных, начиная с самых новых
    game_results = GameResults.query.filter_by(username=player_name).order_by(GameResults.game_datetime.desc()).all()

    if not game_results:
        # Если нет результатов игр, показываем сообщение
        return render_template('final_page.html', message="Нет данных о последних играх.", player_name=player_name)

    # Показываем страницу с историей игр
    return render_template('final_page.html', games=game_results, player_name=player_name)

# Запуск приложения, если этот файл выполняется напрямую
if __name__ == '__main__':
    app.run(debug=True)  # Запускаем сервер в режиме отладки для удобства разработки