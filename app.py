# NextPay - app for tontine groups in Burundi
# I am starting small, I only want to see that Flask runs on my laptop first

from flask import Flask

# this creates my app, everything else will be added to it later
app = Flask(__name__)


# this is a test page, I just want to see a message in my browser
@app.get("/")
def home():
    return "NextPay is running"


# debug=True so the page reloads by itself when I change my code
if __name__ == "__main__":
    app.run(debug=True)