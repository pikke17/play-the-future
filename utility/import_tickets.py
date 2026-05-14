from database import get_connection

def import_file(filename, day):
    conn = get_connection()
    cur = conn.cursor()

    with open(filename, "r") as f:
        tickets = f.read().splitlines()

    for t in tickets:
        try:
            cur.execute(
                "INSERT INTO tickets (ticket_id, has_voted, day) VALUES (?, 0, ?)",
                (t, day)
            )
        except:
            pass

    conn.commit()
    conn.close()

    print(f"Importati ticket Day {day}")

if __name__ == "__main__":
    import_file("tickets_day_1.txt", 1)
    import_file("tickets_day_2.txt", 2)