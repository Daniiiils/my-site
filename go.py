import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash
from yookassa import Configuration, Payment
import uuid
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
l_ = logging.getLogger(__name__)

# Создаём Flask-приложение, указываем папки для шаблонов и статических файлов
app = Flask(__name__, template_folder='htmlki', static_folder='static')
app.secret_key = "klyuch"

# Настройка Yookassa
s = "1066313"
k = "test_Yn_XLgTrbjgis3RjPznkvxaRMQ7kZhS4pbXrGWQ1oj0"
Configuration.configure(s, k)

# Функция для подключения к базе данных
def bd():
    try:
        c = sqlite3.connect("ruinkeepers.db")
        c.row_factory = sqlite3.Row
        return c
    except Exception as e:
        l_.error(f"Ошибка подключения к базе данных: {e}")
        raise

# Инициализация базы данных
def init_db():
    try:
        c = bd()
        c.execute('''
            CREATE TABLE IF NOT EXISTS events (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Название TEXT NOT NULL,
                Дата TEXT NOT NULL,
                Время TEXT NOT NULL,
                Место_сбора TEXT NOT NULL,
                Стоимость REAL NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS participants (
                ID_мероприятия INTEGER,
                Имя TEXT,
                Телефон TEXT,
                Источник TEXT,
                Всего INTEGER,
                Возраст TEXT,
                Дети INTEGER,
                Сумма REAL,
                Новый TEXT,
                Статус_оплаты TEXT,
                Способ_оплаты TEXT,
                Комментарий TEXT,
                Обед TEXT,
                Напоминание TEXT,
                Статус TEXT,
                Подтверждение_оплаты TEXT,
                Результат TEXT,
                Ник TEXT,
                Статус_уведомления TEXT,
                Реквизиты TEXT,
                Статус_возврата TEXT
            )
        ''')
        c.commit()
        c.close()
        l_.info("База данных инициализирована")
    except Exception as e:
        l_.error(f"Ошибка инициализации базы данных: {e}")
        raise

# Вызываем инициализацию при запуске
init_db()

# Главная страница со списком мероприятий
@app.route('/')
def glavn():
    try:
        c = bd()
        m = c.execute("SELECT * FROM events").fetchall()
        c.close()
        return render_template('index.html', m=m)
    except Exception as e:
        l_.error(f"Ошибка в списке мероприятий: {e}")
        flash("Ошибка, не видно мероприятия")
        return render_template('index.html', m=[])

# Страница записи на мероприятие
@app.route('/zapis/<int:i>', methods=['GET', 'POST'])
def zapis(i):
    try:
        c = bd()
        e = c.execute("SELECT * FROM events WHERE ID = ?", (i,)).fetchone()
        if not e:
            flash("Нет такого мероприятия")
            return redirect(url_for('glavn'))

        if request.method == 'POST':
            l_.info("Начало обработки формы")
            nm = request.form['imya'].strip()
            ph = request.form['tel'].strip()
            sr = request.form['otkuda'].strip()
            tl = request.form['skolko']
            ag = request.form.getlist('vozrast')
            ch = request.form['deti']
            nw = request.form['noviy']
            cm = request.form['komment'].strip() if request.form['komment'].strip() else "нету"
            ln = request.form['obed']
            rm = request.form['napominaniya']

            l_.info(f"Получены данные: imya={nm}, tel={ph}, otkuda={sr}, skolko={tl}, vozrast={ag}, deti={ch}, noviy={nw}, komment={cm}, obed={ln}, napominaniya={rm}")

            if not nm or not ph or not sr:
                flash("Заполни имя, телефон и откуда")
                return render_template('zapis.html', e=e)

            try:
                tl = int(tl)
                if tl < 1:
                    raise ValueError("Сколько должно быть больше 0")
            except:
                flash("Сколько должно быть числом и больше 0")
                return render_template('zapis.html', e=e)

            if not ag:
                flash("Выбери возраст")
                return render_template('zapis.html', e=e)

            try:
                ch = int(ch)
                if ch < 0:
                    raise ValueError("Дети не могут быть минус")
            except:
                flash("Дети должно быть числом, 0 или больше")
                return render_template('zapis.html', e=e)

            if nw not in ["da", "net"]:
                flash("Новый должно быть да или нет")
                return render_template('zapis.html', e=e)

            if ln not in ["da", "net"] or rm not in ["da", "net"]:
                flash("Обед и напоминания должно быть да или нет")
                return render_template('zapis.html', e=e)

            ag_str = ", ".join(ag)

            l_.info("Проверки пройдены, начинаем создание платежа")

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
                "description": f"Оплата за мероприятие {i}",
                "metadata": {"i": i}
            }, ik)

            l_.info(f"Платёж создан, id={p.id}, сумма={am}")

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

            l_.info(f"Запись в БД успешна, мероприятие {i}, сумма {am}, id {p.id}")
            return redirect(p.confirmation.confirmation_url)

        c.close()
        return render_template('zapis.html', e=e)

    except Exception as e:
        l_.error(f"Ошибка в записи: {str(e)}")
        flash("Ошибка, попробуй снова")
        return redirect(url_for('glavn'))

# Проверка оплаты
@app.route('/proverka/<int:i>')
def proverka(i):
    try:
        c = bd()
        r = c.execute(
            "SELECT * FROM participants WHERE ID_мероприятия = ? AND Статус_оплаты = 'ozhidaet' ORDER BY rowid DESC LIMIT 1",
            (i,)
        ).fetchone()

        if not r:
            flash("Ошибка, нет записи")
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
            flash("Оплата прошла! Запись подтверждена")
            l_.info(f"Оплата подтверждена, мероприятие {i}, id {p_id}")
        else:
            flash("Оплата не прошла, попробуй снова")
            l_.info(f"Оплата не прошла, мероприятие {i}, id {p_id}, status {p.status}")

        c.close()
        return redirect(url_for('glavn'))

    except Exception as e:
        l_.error(f"Ошибка в проверке: {str(e)}")
        flash("Ошибка при проверке оплаты")
        return redirect(url_for('glavn'))