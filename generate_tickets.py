import random
import string
import os
import qrcode
from database import get_connection

# URL base (CAMBIA quando vai online)
BASE_URL = "https://play-the-future-vfu.up.railway.app/vote/"


def generate_ticket():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def reset_votes():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM votes")

    conn.commit()
    conn.close()

    print("✅ Tabella votes svuotata")

def insert_and_generate(count, day):
    conn = get_connection()
    cur = conn.cursor()

    inserted = 0

    # cartella QR
    qr_dir = f"qr_day_{day}"
    os.makedirs(qr_dir, exist_ok=True)

    # file lista ticket
    with open(f"tickets_day_{day}.txt", "w") as f:

        while inserted < count:
            ticket = generate_ticket()

            try:
                # inserisci nel DB
                cur.execute(
                    "INSERT INTO tickets (ticket_id, has_voted, day) VALUES (?, 0, ?)",
                    (ticket, day)
                )

                # salva nel file
                f.write(ticket + "\n")

                # genera QR
                url = BASE_URL + ticket
                img = qrcode.make(url)

                # ridimensiona (più leggibile)
                img = img.resize((300, 300))

                img.save(f"{qr_dir}/{ticket}.png")

                inserted += 1

            except:
                # duplicato → ignora
                pass

    conn.commit()
    conn.close()

    print(f"✅ {count} ticket + QR creati per Day {day}")


if __name__ == "__main__":
    reset_votes()
    insert_and_generate(500, 1)
    insert_and_generate(500, 2)