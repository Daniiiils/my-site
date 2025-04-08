from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from yookassa import Configuration, Payment
import uuid
import logging

logging.basicConfig(level=logging.INFO)
l = logging.getLogger(__name__)

a = Flask(__name__, static_folder='stil')
a.template_folder = 'htmlki'
a.secret_key = "klyuch"

s = "1066313"
k = "test_Yn_XLgTrbjgis3RjPznkvxaRMQ7kZhS4pbXrGWQ1oj0"
Configuration.configure(s, k)

def bd():
    try:
        c = sqlite3.connect("ruinkeepers.db")
        c.row_factory = sqlite3.Row
        return c
    except:
        l.error("bd oshibka")
        raise

@a.route('/')
def glavn():
    try:
        c = bd()
        m = c.execute("SELECT * FROM events").fetchall()
        c.close()
        return render_template('index.html', m=m)
    except:
        l.error("oshibka v spiske")
        flash("oshibka, ne vidno meropriyatiya")
        return render_template('index.html', m=[])

@a.route('/zapis/<int:i>', methods=['GET', 'POST'])
def zapis(i):
    try:
        c = bd()
        e = c.execute("SELECT * FROM events WHERE ID = ?", (i,)).fetchone()
        if not e:
            flash("net takogo meropriyatiya")
            return redirect(url_for('glavn'))

        if request.method == 'POST':
            l.info("nachalo obrabotki formy")
            nm = request.form['imya'].strip()
            ph = request.form['tel'].strip()
            sr = request.form['otkuda'].strip()
            tl = request.form['skolko']
            ag = request.form.getlist('vozrast')
            ch = request.form['deti']
            nw = request.form['noviy']
            cm = request.form['komment'].strip() if request.form['komment'].strip() else "netu"
            ln = request.form['obed']
            rm = request.form['napominaniya']

            l.info(f"polucheny dannye: imya={nm}, tel={ph}, otkuda={sr}, skolko={tl}, vozrast={ag}, deti={ch}, noviy={nw}, komment={cm}, obed={ln}, napominaniya={rm}")

            if not nm or not ph or not sr:
                flash("zapolni imya, tel i otkuda")
                return render_template('zapis.html', e=e)

            try:
                tl = int(tl)
                if tl < 1:
                    raise ValueError("skolko dolzhno byt bolshe 0")
            except:
                flash("skolko dolzhno byt chislo i bolshe 0")
                return render_template('zapis.html', e=e)

            if not ag:
                flash("vyberi vozrast")
                return render_template('zapis.html', e=e)

            try:
                ch = int(ch)
                if ch < 0:
                    raise ValueError("deti ne mogut byt minus")
            except:
                flash("deti dolzhno byt chislo, 0 ili bolshe")
                return render_template('zapis.html', e=e)

            if nw not in ["da", "net"]:
                flash("noviy dolzhno byt da ili net")
                return render_template('zapis.html', e=e)

            if ln not in ["da", "net"] or rm not in ["da", "net"]:
                flash("obed i napominaniya dolzhno byt da ili net")
                return render_template('zapis.html', e=e)

            ag_str = ", ".join(ag)

            l.info("proverki proideny, nachinaem sozdanie platezha")

            cena = float(e['Стоимость'])
            am = cena * tl

            ik = str(uuid.uuid4())
            p = Payment.create({
                "amount": {
                    "value": f"{am:.2f}",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": url_for('proverka', i=i, _external=True)
                },
                "capture": True,
                "description": f"oplata za meropriyatiye {i}",
                "metadata": {"i": i}
            }, ik)

            l.info(f"platezh sozdan, id={p.id}, summa={am}")

            c.execute('''
                INSERT INTO participants (
                    ID_мероприятия, Имя, Телефон, Источник, Всего, Возраст,
                    Дети, Сумма, Новый, Статус_оплаты, Способ_оплаты, Комментарий,
                    Обед, Напоминание, Статус, Подтверждение_оплаты, Результат, Ник, Статус_уведомления,
                    Реквизиты, Статус_возврата
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                i, nm, ph, sr, tl, ag_str, ch,
                am, nw, "ozhidaet", "netu", cm, ln, rm,
                "ozhidaet", p.id, "aktiv", "", "ozhidaet", "", "ne nachato"
            ))
            c.commit()
            c.close()

            l.info(f"zapis v bd uspeshno, meropriyatiye {i}, summa {am}, id {p.id}")
            return redirect(p.confirmation.confirmation_url)

        c.close()
        return render_template('zapis.html', e=e)

    except Exception as e:
        l.error(f"oshibka v zapisi: {str(e)}")
        flash("oshibka, poprobuy snova")
        return redirect(url_for('glavn'))

@a.route('/proverka/<int:i>')
def proverka(i):
    try:
        c = bd()
        r = c.execute(
            "SELECT * FROM participants WHERE ID_мероприятия = ? AND Статус_оплаты = 'ozhidaet' ORDER BY rowid DESC LIMIT 1",
            (i,)
        ).fetchone()

        if not r:
            flash("oshibka, net zapisi")
            return redirect(url_for('glavn'))

        p_id = r['Подтверждение_оплаты']
        p = Payment.find_one(p_id)

        if p.status == "succeeded":
            c.execute('''
                UPDATE participants
                SET Статус_оплаты = ?, Способ_оплаты = ?, Сумма = ?, Статус = ?
                WHERE Подтверждение_оплаты = ?
            ''', (
                "oplacheno", p.payment_method.type, float(p.amount.value),
                "podtverzhdeno", p_id
            ))
            c.commit()
            flash("oplata proshla! zapis podtverzhdena")
            l.info(f"oplata podtverzhdena, meropriyatiye {i}, id {p_id}")
        else:
            flash("oplata ne proshla, poprobuy snova")
            l.warning(f"oplata ne proshla, meropriyatiye {i}, id {p_id}, status {p.status}")

        c.close()
        return redirect(url_for('glavn'))

    except:
        l.error("oshibka v proverke")
        flash("oshibka pri proverke oplaty")
        return redirect(url_for('glavn'))

if __name__ == "__main__":
    a.run(debug=True, host='0.0.0.0', port=5000)
