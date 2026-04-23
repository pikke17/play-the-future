from flask import Flask, render_template, request
from database import init_db, get_connection

app = Flask(__name__)

init_db()

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/vote/<ticket_id>")
def vote(ticket_id):
   
    conn = get_connection()
    cur = conn.cursor()

    # check if ticket exists
    cur.execute("SELECT has_voted FROM tickets WHERE ticket_id = ?", (ticket_id,))
    row = cur.fetchone()

    if row is None:
        # new ticket
        cur.execute(
            "INSERT INTO tickets (ticket_id, has_voted) VALUES (?, 0)",
            (ticket_id,)
        )
        conn.commit()
    else:
        # ticket already used
        if row[0] == 1:
            conn.close()
            return "Hai già votato con questo ticket."

    conn.close()

    singers = [
        "Cantante 1",
        "Cantante 2",
        "Cantante 3"
    ]
    return render_template("vote.html", singers=singers, ticket_id=ticket_id)

@app.route("/submit", methods=["POST"])
def submit():
    # read vote
    singer = request.form.get("singer")

    # read ticket
    ticket_id = request.form.get("ticket_id")

    if singer is None:
        return "Errore: nessun cantante selezionato", 400
    
    conn = get_connection()
    cur = conn.cursor()

    # check ticket
    cur.execute("SELECT has_voted FROM tickets WHERE ticket_id = ?", (ticket_id,))
    row = cur.fetchone()

    if row is None:
        conn.close()
        return "Ticket non valido", 400

    if row[0] == 1:
        conn.close()
        return "Hai già votato con questo ticket."

    # save vote
    cur.execute(
        "INSERT INTO votes (ticket_id, singer) VALUES (?, ?)",
        (ticket_id, singer)
    )

    # use tickets
    cur.execute(
        "UPDATE tickets SET has_voted = 1 WHERE ticket_id = ?",
        (ticket_id,)
    )

    conn.commit()
    conn.close()

    return f"Hai votato: {singer}. Codice ticket: {ticket_id}"

@app.route("/results")
def results():
    conn = get_connection()
    cur = conn.cursor()

    # counting votes
    cur.execute("""
        SELECT singer, COUNT(*) as total
        FROM votes
        GROUP BY singer
        ORDER BY total DESC
    """)
    results = cur.fetchall()

    conn.close()

    return render_template("results.html", results=results)

if __name__ == "__main__":
    app.run(debug=True)
