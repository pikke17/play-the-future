from flask import Flask, render_template, request, redirect, session, url_for
from database import init_db, get_connection
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "leccheria69")

init_db()

#import tickets
from database import get_connection
from utility.import_tickets import import_file

conn = get_connection()
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM tickets")
count = cur.fetchone()[0]
conn.close()

if count == 0:
    import_file("tickets_day_1.txt", 1)
    import_file("tickets_day_2.txt", 2)

#----------USER----------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/vote/<ticket_id>")
def vote(ticket_id):

    conn = get_connection()
    cur = conn.cursor()

    # ✅ 1. controlla ticket + recupera day
    cur.execute(
        "SELECT has_voted, day FROM tickets WHERE ticket_id = ?",
        (ticket_id,)
    )
    row = cur.fetchone()

    # ❌ ticket inesistente
    if row is None:
        conn.close()
        return "Ticket non valido", 400

    has_voted = row[0]
    ticket_day = row[1]

    # ✅ 2. controlla televoto per quel day
    if not is_televoting_active(ticket_day):
        conn.close()
        return render_template(
            "televoting_closed.html",
            day=ticket_day
        )

    # ✅ 3. controlla se ha già votato
    if has_voted == 1:
        conn.close()
        return render_template(
            "vote_ko.html",
            singer=get_vote(ticket_id),
            ticket_id=ticket_id
        )

    # ✅ 4. carica cantanti del day del ticket
    cur.execute("""
        SELECT id, firstName, lastName, songTitle, songAuthor
        FROM singers
        WHERE day = ?
    """, (ticket_day,))

    singers = cur.fetchall()

    conn.close()

    if not singers:
        return "Nessun cantante disponibile per questa serata."

    # ✅ 5. mostra pagina voto con day
    return render_template(
        "vote.html",
        ticket_id=ticket_id,
        singers=singers,
        day=ticket_day
    )

@app.route("/submit", methods=["POST"])
def submit():
    
    action = request.form.get("action")
    ticket_id = request.form.get("ticket_id")
    singer_id = request.form.get("singer_id")

    # ✅ RESET VOTO
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

    # ✅ recupera ticket + day
    cur.execute(
        "SELECT has_voted, day FROM tickets WHERE ticket_id = ?",
        (ticket_id,)
    )
    row = cur.fetchone()

    if row is None:
        conn.close()
        return "Ticket non valido", 400

    has_voted = row[0]
    ticket_day = row[1]

    # ✅ controllo doppio voto
    if has_voted == 1:
        conn.close()
        return render_template(
            "vote_ko.html",
            singer=get_vote(ticket_id),
            ticket_id=ticket_id
        )

    # ✅ controllo sicurezza (opzionale ma consigliato)
    cur.execute(
        "SELECT id FROM singers WHERE id = ? AND day = ?",
        (singer_id, ticket_day)
    )
    if cur.fetchone() is None:
        conn.close()
        return "Errore: cantante non valido per questa serata", 400

    # ✅ salva voto con DAY CORRETTO
    cur.execute(
        "INSERT INTO votes (ticket_id, singer_id, day) VALUES (?, ?, ?)",
        (ticket_id, singer_id, ticket_day)
    )

    # ✅ blocca ticket
    cur.execute(
        "UPDATE tickets SET has_voted = 1 WHERE ticket_id = ?",
        (ticket_id,)
    )

    conn.commit()
    conn.close()

    return render_template(
        "vote_ok.html",
        singer=get_vote(ticket_id),
        ticket_id=ticket_id
    )

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
    day = get_current_day()
    cur.execute("""
        SELECT
            s.id,
            s.firstName,
            s.lastName,
            s.songTitle,
            s.songAuthor,
            COUNT(v.id) AS votesCount
        FROM singers s
        LEFT JOIN votes v 
            ON s.id = v.singer_id
            AND v.day = ?
        WHERE s.day = ?
        GROUP BY s.id
        ORDER BY votesCount DESC
    """, (day, day))
    rows = cur.fetchall()

    
    day = get_current_day()

    cur.execute("SELECT COUNT(*) FROM votes WHERE day = ?", (day,))
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
        televoting_active=is_televoting_active(get_current_day()),
        current_day=get_current_day()
    )

@app.route("/admin/televoting/start", methods=["POST"])
def televoting_start():
    if not session.get("admin_logged"):
        return redirect(url_for("admin"))

    set_televoting_active(get_current_day(), True)
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/televoting/stop", methods=["POST"])
def televoting_stop():
    if not session.get("admin_logged"):
        return redirect(url_for("admin"))

    set_televoting_active(get_current_day(), False)
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/reset")
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

        day = request.form.get("day")

        cur.execute("""
            INSERT INTO singers 
            (firstName, lastName, songTitle, songAuthor, day)
            VALUES (?, ?, ?, ?, ?)
        """, (firstName, lastName, songTitle, songAuthor, day))
        conn.commit()

    # singers list
    cur.execute("""
    SELECT
        s.id,
        s.firstName,
        s.lastName,
        s.songTitle,
        s.songAuthor,
        s.day,
        COUNT(v.id) AS votes
    FROM singers s
    LEFT JOIN votes v ON s.id = v.singer_id
    GROUP BY s.id
    ORDER BY s.day, s.firstName, s.lastName
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

from flask import Response
@app.route("/admin/singers/export")
def export_singers():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT firstName, lastName, songTitle, songAuthor, day
        FROM singers
        ORDER BY day, firstName
    """)

    rows = cur.fetchall()
    conn.close()

    # costruzione CSV
    lines = ["firstName,lastName,songTitle,songAuthor,day"]

    for r in rows:
        lines.append(",".join([
            r[0] or "",
            r[1] or "",
            r[2] or "",
            r[3] or "",
            str(r[4])
        ]))

    csv_data = "\n".join(lines)

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=singers.csv"}
    )

import csv
import io
@app.route("/admin/singers/import", methods=["POST"])
def import_singers():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    file = request.files.get("file")

    if not file:
        return "File mancante", 400

    stream = io.StringIO(file.stream.read().decode("UTF-8"))
    reader = csv.DictReader(stream)

    conn = get_connection()
    cur = conn.cursor()

    for row in reader:
        try:
            cur.execute("""
                INSERT INTO singers (firstName, lastName, songTitle, songAuthor, day)
                VALUES (?, ?, ?, ?, ?)
            """, (
                row["firstName"],
                row["lastName"],
                row["songTitle"],
                row["songAuthor"],
                int(row["day"])
            ))
        except:
            pass  # ignora duplicati/errori

    conn.commit()
    conn.close()

    return redirect(url_for("admin_singers"))

@app.route("/admin/day/<int:day>", methods=["POST"])
def change_day(day):
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))

    set_current_day(day)
    return redirect(url_for("admin_dashboard"))

#----------PRIVATE FUNCTIONS----------
def is_televoting_active(day):
    conn = get_connection()
    cur = conn.cursor()

    key = f"televoting_active_day_{day}"

    cur.execute("SELECT value FROM config WHERE key = ?", (key,))
    row = cur.fetchone()

    conn.close()
    return row and row[0] == "1"

def set_televoting_active(day, active: bool):
    conn = get_connection()
    cur = conn.cursor()

    key = f"televoting_active_day_{day}"
    value = "1" if active else "0"

    cur.execute(
        "UPDATE config SET value = ? WHERE key = ?",
        (value, key)
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

def get_current_day():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM config WHERE key = 'current_day'")
    row = cur.fetchone()
    conn.close()
    return int(row[0]) if row else 1

def set_current_day(day: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE config SET value = ? WHERE key = 'current_day'",
        (str(day),)
    )
    conn.commit()
    conn.close()

if __name__ == "__main__":
    app.run(debug=True)
