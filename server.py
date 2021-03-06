import json, os
from flask import Flask, render_template
from flask_socketio import SocketIO, send, emit
from flask_pymongo import MongoClient
from hangman import player

def get_cred():
	pw = ''
	with open('hangman.config', 'r') as f:
		pw = f.readline().strip()
	return pw

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 1
socketio = SocketIO(app)
pw = get_cred()
mongo = MongoClient('mongodb://admin:' + pw + '@ds137090.mlab.com:37090/hangman-bot')
p = player.HangmanPlayer()
db = mongo['hangman-bot']
bots = db['bot-statistics']

port = int(os.environ.get("PORT", 5000))


@app.route('/')
def render_page():
	return render_template('index.html')


@socketio.on('play_game')
def play_game(msg):
	p.start_new_game()
	emit('game_state', json.dumps(p.game.get_state()))
	emit('new_game', json.dumps({
		'word': p.game.word,
		'word_length': len(p.game.word),
		'max_guesses': p.game.guesses,
		'word_list': [w for w in p.g.words if len(w) == len(p.game.word)]
		}))


@socketio.on('letter_guess')
def guess(letter):
	p.game.process_letter_guess(letter)
	emit('game_state', json.dumps(p.game.get_state()))
	emit('processed', 'true')
	if p.game.game_over():
		emit('win_status', p.game.check_for_win_status())
		results = p.run_solvers()
		success_rates = list(update_bot_stats(results))
		printable = [p.report_solver_results(s, r) for s, r in results]
		zipped = ['{} (Cumulative success rate: {})'.format(res, round(rate, 5)) for res, rate in zip(printable, success_rates)]
		emit('solver_results', zipped)


def update_bot_stats(results):
	for s, r in results:
		if r['win']:
			bots.find_one_and_update({'name': s.__name__}, {'$inc': {'wins': 1, 'losses': 0, 'success': 0.0}}, upsert=True)
		else:
			bots.find_one_and_update({'name': s.__name__}, {'$inc': {'losses': 1, 'wins': 0, 'success': 0.0}}, upsert=True)
		bot = bots.find_one({'name':s.__name__})
		wins, losses = bot['wins'], bot['losses']
		success_rate = wins / (wins + losses)
		bots.find_one_and_update({'name': s.__name__}, {'$set': {'success': success_rate}}, upsert=True)
		yield success_rate


if __name__ == '__main__':
    socketio.run(app)
    # port = int(os.environ.get("PORT", 5000))
    # console.log(os.environ.get("PORT"))
    # app.run(host='0.0.0.0', port=port)