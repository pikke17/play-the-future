from flask import Flask, render_template, request, redirect, session, url_for
from database import init_db, get_connection
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "leccheria69")

init_db()

#----------USER----------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/vote/<ticket_id>")
def vote(ticket_id):
    
    if not is_televoting_active():
        return render_template("televoting_closed.html")

    conn = get_connection()
    cur = conn.cursor()

    # check ticket
    cur.execute(
        "SELECT has_voted FROM tickets WHERE ticket_id = ?",
        (ticket_id,)
    )
    row = cur.fetchone()

    if row is None:
        # new ticket
        cur.execute(
            "INSERT INTO tickets (ticket_id, has_voted) VALUES (?, 0)",
            (ticket_id,)
        )
        conn.commit()
    elif row[0] == 1:
        conn.close()
        return render_template(
            "vote_ko.html",
            singer=get_vote(ticket_id),
            ticket_id=ticket_id)

    # load singers
    cur.execute("SELECT id, firstName, lastName, songTitle, songAuthor FROM singers")
    singers = cur.fetchall()

    conn.close()

    if not singers:
        return "Nessun cantante disponibile al momento."

    # vote page
    return render_template(
        "vote.html",
        ticket_id=ticket_id,
        singers=singers
    )

@app.route("/submit", methods=["POST"])
def submit():
    
    action = request.form.get("action")
    ticket_id = request.form.get("ticket_id")
    singer_id = request.form.get("singer_id")

    
    if action == "reset_vote":
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("DELETE FROM votes WHERE ticket_id = ?", (ticket_id,))
        cur.execute("UPDATE tickets SET has_voted = 0 WHERE ticket_id = ?", (ticket_id,))

        conn.commit()
        conn.close()

        return redirect(url_for("vote", ticket_id=ticket_id))


    if not ticket_id or not singer_id:
        return "Dati mancanti", 400

    conn = get_connection()
    cur = conn.cursor()

    # check ticket
    cur.execute(
        "SELECT has_voted FROM tickets WHERE ticket_id = ?",
        (ticket_id,)
    )
    row = cur.fetchone()

    if row is None:
        conn.close()
        return "Ticket non valido", 400

    if row[0] == 1:
        conn.close()
        return render_template(
            "vote_ko.html",
            singer=get_vote(ticket_id),
            ticket_id=ticket_id
            )

    # save vote
    cur.execute(
        "INSERT INTO votes (ticket_id, singer_id) VALUES (?, ?)",
        (ticket_id, singer_id)
    )

    # lock ticket
    cur.execute(
        "UPDATE tickets SET has_voted = 1 WHERE ticket_id = ?",
        (ticket_id,)
    )

    conn.commit()
    conn.close()

    print("RESET -> ticket_id:", ticket_id)
    return render_template(
        "vote_ok.html",
        singer=get_vote(ticket_id),
        ticket_id=ticket_id)

#----------ADMIN----------
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        password = request.form.get("password")

        if password == ADMIN_PASSWORD:
            session["admin_logged"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            return render_template("admin_login.html", error=True)

    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged", None)
    return redirect(url_for("admin_dashboard"))

@app.route("/admin_dashboard")
def admin_dashboard():

    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    conn = get_connection()
    cur = conn.cursor()

    # results
    cur.execute("""
        SELECT
            s.id,
            s.firstName,
            s.lastName,
            s.songTitle,
            s.songAuthor,
            COUNT(v.id) AS votesCount
        FROM singers s
        LEFT JOIN votes v ON s.id = v.singer_id
        GROUP BY s.id
        ORDER BY votesCount DESC
    """)
    rows = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM votes")
    total_votes = cur.fetchone()[0]

    results = []
    for r in rows:
        votes = r[5]
        percentage = (votes / total_votes * 100) if total_votes > 0 else 0
        results.append({
            "id": r[0],
            "firstName": r[1],
            "lastName": r[2],
            "songTitle":r[3],
            "songAuthor":r[4],
            "votes": votes,
            "percentage": round(percentage, 3)
        })

    conn.close()

    return render_template(
        "admin_dashboard.html",
        results=results,
        total_votes=total_votes,
        televoting_active=is_televoting_active()
    )

@app.route("/admin/televoting/start", methods=["POST"])
def televoting_start():
    if not session.get("admin_logged"):
        return redirect(url_for("admin"))

    set_televoting_active(True)
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/televoting/stop", methods=["POST"])
def televoting_stop():
    if not session.get("admin_logged"):
        return redirect(url_for("admin"))

    set_televoting_active(False)
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/reset", methods=["POST"])
def admin_reset():
    
    if not session.get("admin_logged"):
        return redirect(url_for("admin"))

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM votes")

    cur.execute("UPDATE tickets SET has_voted = 0")

    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))

@app.route("/admin/singers", methods=["GET", "POST"])
def admin_singers():
    if not session.get("admin_logged"):
        return redirect(url_for("admin"))

    conn = get_connection()
    cur = conn.cursor()

    # new singer
    if request.method == "POST":
        firstName = request.form.get("firstName")
        lastName = request.form.get("lastName")
        songTitle = request.form.get("songTitle")
        songAuthor = request.form.get("songAuthor")

        # normalizza lastName (evita None)
        lastName = lastName if lastName else ""

        if firstName and songTitle and songAuthor:
            cur.execute("INSERT INTO singers (firstName, lastName, songTitle, songAuthor) VALUES (?, ?, ?, ?)",
                (firstName, lastName, songTitle, songAuthor)
            )
            conn.commit()

    # singers list
    cur.execute("""
        SELECT
            s.id,
            s.firstName,
            s.lastName,
            s.songTitle,
            s.songAuthor,
            COUNT(v.id) AS votes
        FROM singers s
        LEFT JOIN votes v ON s.id = v.singer_id
        GROUP BY s.id
        ORDER BY s.firstName, s.lastName
    """)
    singers = cur.fetchall()

    conn.close()

    return render_template("admin_singers.html", singers=singers)

@app.route("/admin/singers/delete/<int:id>")
def delete_singer(id):
    if not session.get("admin_logged"):
        return redirect(url_for("admin"))

    conn = get_connection()
    cur = conn.cursor()

    # check if siger has votes
    cur.execute("SELECT COUNT(*) FROM votes WHERE singer_id = ?", (id,))
    votes_count = cur.fetchone()[0]

    if votes_count == 0:
        cur.execute("DELETE FROM singers WHERE id = ?", (id,))
        conn.commit()

    conn.close()
    return redirect(url_for("admin_singers"))

@app.route("/admin/singers/edit/<int:id>", methods=["GET", "POST"])
def edit_singer(id):
    if not session.get("admin_logged"):
        return redirect(url_for("admin"))

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM votes WHERE singer_id = ?", (id,))
    votes_count = cur.fetchone()[0]

    if votes_count > 0:
        conn.close()
        return "❌ Impossibile modificare: questo cantante ha già ricevuto voti"

    if request.method == "POST":
        firstName = request.form.get("firstName")
        lastName = request.form.get("lastName")
        songTitle = request.form.get("songTitle")
        songAuthor = request.form.get("songAuthor")
      
        # normalizza lastName (evita None)
        lastName = lastName if lastName else ""

        if firstName and songTitle and songAuthor:
            cur.execute("""
                UPDATE singers
                SET firstName = ?, lastName = ?, songTitle = ?, songAuthor = ?
                WHERE id = ?
            """, (firstName, lastName, songTitle, songAuthor, id))
            conn.commit()

        conn.close()
        return redirect(url_for("admin_singers"))

    cur.execute("SELECT * FROM singers WHERE id = ?", (id,))
    singer = cur.fetchone()
    conn.close()

    if not singer:
        return "Cantante non trovato", 404

    return render_template("admin_singers_edit.html", singer=singer)

#----------PRIVATE FUNCTIONS----------
def is_televoting_active():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT value FROM config WHERE key = 'televoting_active'"
    )
    row = cur.fetchone()
    conn.close()
    return row and row[0] == "1"

def set_televoting_active(active: bool):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE config SET value = ? WHERE key = 'televoting_active'",
        ("1" if active else "0",)
    )
    conn.commit()
    conn.close()

def get_vote(ticket_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            s.firstName,
            s.lastName,
            s.songTitle,
            s.songAuthor
        FROM votes v
        JOIN singers s ON v.singer_id = s.id
        WHERE v.ticket_id = ?
        LIMIT 1
    """, (ticket_id,))

    singer = cur.fetchone()
    conn.close()

    return singer

def reset_vote(ticket_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM votes WHERE ticket_id = ?", (ticket_id,))

    cur.execute("""
        UPDATE tickets
        SET has_voted = 0
        WHERE ticket_id = ?
    """, (ticket_id,))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    app.run(debug=True)
