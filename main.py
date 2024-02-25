
from flask import Flask, render_template, request, redirect, url_for, jsonify
import random
import os
import json
import requests
from flask_caching import Cache
from flask_socketio import SocketIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
USER_FOLDER = 'static/users'
DIET_CHART_FOLDER = 'static/diet_charts'

if not os.path.exists(USER_FOLDER):
    os.makedirs(USER_FOLDER)
if not os.path.exists(DIET_CHART_FOLDER):
    os.makedirs(DIET_CHART_FOLDER)

socketio = SocketIO(app)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

SPORTS_ACTIVITIES = [
    ('Running', 'km'),
    ('Cycling', 'km'),
    ('Swimming', 'laps'),
    ('Basketball', 'points'),
    ('Football', 'goals')
]

ACTIVITIES = {
    'pushup': 60,
    'situp': 45,
    'front_press': 30
}

activity_timers = {}

def save_participant_data(data):
    data_file_path = os.path.join('static', 'participant_data.json')
    with open(data_file_path, 'w') as file:
        json.dump(data, file)

def calculate_random_fitness(prev_fitness):
    return prev_fitness + random.randint(1, 3)

def get_user_data(username):
    user_file_path = os.path.join(USER_FOLDER, f'{username}.json')
    if os.path.exists(user_file_path):
        with open(user_file_path, 'r') as file:
            return json.load(file)
    else:
        return None

def save_user_data(username, data):
    user_file_path = os.path.join(USER_FOLDER, f'{username}.json')
    with open(user_file_path, 'w') as file:
        json.dump(data, file)

def get_nutritional_info(food_name):
    api_key = 'ZQbcDZv018xRlou2ApjsgXwfzuy2s9OohWnoYNHz'
    url = f'https://api.nal.usda.gov/fdc/v1/foods/search?query={food_name}&api_key={api_key}'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if 'foods' in data and len(data['foods']) > 0:
            food = data['foods'][0]
            nutritional_info = {}
            for nutrient in food['foodNutrients']:
                if nutrient['nutrientName'] == 'Energy' and nutrient['unitName'] == 'KCAL':
                    nutritional_info['calories'] = nutrient['value']
                elif nutrient['nutrientName'] == 'Protein' and nutrient['unitName'] == 'G':
                    nutritional_info['protein'] = nutrient['value']
                elif nutrient['nutrientName'] == 'Fat' and nutrient['unitName'] == 'G':
                    nutritional_info['fat'] = nutrient['value']
                elif nutrient['nutrientName'] == 'Carbohydrate, by difference' and nutrient['unitName'] == 'G':
                    nutritional_info['carbohydrate'] = nutrient['value']
                elif nutrient['nutrientName'] == 'Total Sugars' and nutrient['unitName'] == 'G':
                    nutritional_info['sugar'] = nutrient['value']
                elif nutrient['nutrientName'] == 'Fiber' and nutrient['unitName'] == 'G':
                    nutritional_info['fiber'] = nutrient['value']
                elif nutrient['nutrientName'] == 'Calcium, Ca' and nutrient['unitName'] == 'MG':
                    nutritional_info['calcium'] = nutrient['value']
            return nutritional_info
        else:
            return None
    else:
        return None
def save_participant_data(participant_data):
    data_file_path = os.path.join('static', 'participant_data.json')
    if os.path.exists(data_file_path):
        with open(data_file_path, 'r') as file:
            existing_data = json.load(file)
            if isinstance(existing_data, list):
                existing_data.append(participant_data)
            else:
                existing_data = [existing_data, participant_data]
        with open(data_file_path, 'w') as file:
            json.dump(existing_data, file)
    else:
        with open(data_file_path, 'w') as file:
            json.dump([participant_data], file)
@app.route('/timers', methods=['GET', 'POST'])
def view_timers():
    if request.method == 'POST':
        participant_data = request.form.to_dict()
        save_participant_data(participant_data)
        return redirect(url_for('view_timers'))
    else:
        data_file_path = os.path.join('static', 'participant_data.json')
        if os.path.exists(data_file_path):
            with open(data_file_path, 'r') as file:
                participant_data = json.load(file)
                if isinstance(participant_data, list):
                    participant_data = {str(i): data for i, data in enumerate(participant_data)}
        else:
            participant_data = {}
        return render_template('timers.html', participant_data=participant_data)

@app.route('/search_timers', methods=['POST'])
def search_timers():
    if request.method == 'POST':
        search_name = request.form['search_name']
        data_file_path = os.path.join('static', 'participant_data.json')
        if os.path.exists(data_file_path):
            with open(data_file_path, 'r') as file:
                participant_data = json.load(file)
            filtered_participants = {name: data for name, data in participant_data.items() if search_name.lower() in name.lower()}
            return render_template('timers.html', participant_data=filtered_participants)
        else:
            return "No participant data found."

@app.route('/')
@cache.cached(timeout=60)
def home():
    return render_template('index.html', SPORTS_ACTIVITIES=SPORTS_ACTIVITIES)

@app.route('/add_user', methods=['POST'])
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        if username:
            user_file_path = os.path.join(USER_FOLDER, f'{username}.json')
            if not os.path.exists(user_file_path):
                with open(user_file_path, 'w') as file:
                    data = {'username': username, 'fitness': {activity[0]: {'target': 0, 'achieved': 0} for activity in SPORTS_ACTIVITIES}}
                    json.dump(data, file)
                return redirect(url_for('home'))
            else:
                return "User already exists!"
        else:
            return "Invalid username"

@app.route('/add_activity', methods=['POST'])
def add_activity():
    if request.method == 'POST':
        username = request.form['username']
        activity = request.form['activity']
        achieved = int(request.form.get('achieved', 0))  # Get the achieved value if provided, default to 0
        user_data = get_user_data(username)
        if user_data and activity in user_data['fitness']:
            user_data['fitness'][activity]['achieved'] = achieved
            save_user_data(username, user_data)
            socketio.emit('update_fitness', {'username': username, 'fitness_data': user_data['fitness']})
            return redirect(url_for('home'))
        else:
            return "User not found or activity does not exist"

@app.route('/search_user', methods=['POST'])
def search_user():
    if request.method == 'POST':
        username = request.form['username']
        user_data = get_user_data(username)
        if user_data:
            fitness_targets = {}
            for activity, unit in SPORTS_ACTIVITIES:
                fitness_targets[activity] = {'target': calculate_random_fitness(random.randint(1, 10)), 'unit': unit}
            user_data['fitness_targets'] = fitness_targets
            previous_fitness_data = {}
            if 'fitness' in user_data:
                previous_fitness_data = {activity: data.get('achieved', 0) for activity, data in user_data['fitness'].items()}
            return render_template('fitness_comparison.html', username=username, fitness_data=user_data['fitness'], previous_fitness_data=previous_fitness_data, fitness_targets=fitness_targets)
        else:
            return jsonify({'error': 'User not found'})

@app.route('/set_goal', methods=['POST'])
def set_goal():
    if request.method == 'POST':
        username = request.form['username']
        activity = request.form['activity']
        target = int(request.form['target'])
        user_data = get_user_data(username)
        if user_data and activity in user_data['fitness']:
            user_data['fitness'][activity]['target'] = target
            save_user_data(username, user_data)
            return redirect(url_for('home'))
        else:
            return "User not found or activity does not exist"

@app.route('/compare_fitness', methods=['GET'])
@cache.cached(timeout=60)
def compare_fitness():
    fitness_targets = {}
    for activity, unit in SPORTS_ACTIVITIES:
        fitness_targets[activity] = {'target': calculate_random_fitness(random.randint(1, 10)), 'unit': unit}
    return render_template('fitness_comparison.html', fitness_targets=fitness_targets)

@app.route('/food', methods=['GET', 'POST'])
def food():
    if request.method == 'POST':
        food_name = request.form['food_name']
        nutritional_info = get_nutritional_info(food_name)
        return render_template('food.html', food_name=food_name, nutritional_info=nutritional_info)
    else:
        return render_template('food.html')

@app.route('/diet_chart', methods=['GET', 'POST'])
def diet_chart():
    if request.method == 'POST':
        user_name = request.form['user_name']
        breakfast = request.form['breakfast']
        lunch = request.form['lunch']
        dinner = request.form['dinner']
        snacks = request.form['snacks']
        diet_plan = {
            'breakfast': breakfast,
            'lunch': lunch,
            'dinner': dinner,
            'snacks': snacks
        }
        diet_chart_file = os.path.join(DIET_CHART_FOLDER, f'{user_name}_diet_chart.json')
        with open(diet_chart_file, 'w') as file:
            json.dump(diet_plan, file)
        return redirect(url_for('diet_chart'))
    return render_template('diet_chart_form.html')

@app.route('/diet_chart/<user_name>', methods=['GET'])
def view_diet_chart(user_name):
    diet_chart_file = os.path.join(DIET_CHART_FOLDER, f'{user_name}_diet_chart.json')
    if os.path.exists(diet_chart_file):
        with open(diet_chart_file, 'r') as file:
            diet_plan = json.load(file)
        return render_template('view_diet_chart.html', user_name=user_name, diet_plan=diet_plan)
    else:
        return "Diet chart not found for this user."

if __name__ == '__main__':
    socketio.run(app, debug=True)


