from flask import Flask

app = Flask(__name__)

@app.route('/process', methods=['GET', 'POST'])
def process():
    return "Worker processed the data!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6002)