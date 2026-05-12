from flask import Flask, render_template, redirect, url_for, flash, request, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from PIL import Image, ImageDraw, ImageFont
import random
import os
from datetime import datetime
import textwrap
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FileField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
import shutil
import glob


app = Flask(__name__, template_folder='htmls', instance_path=None, instance_relative_config=False)
app.config.from_object(Config)

db = SQLAlchemy(app)
lm = LoginManager(app)
lm.login_view = 'login'
lm.login_message = ''

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TEMPLATE_FOLDER'], exist_ok=True)
os.makedirs(app.config['GENERATED_FOLDER'], exist_ok=True)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    mail = db.Column(db.String(120), unique=True, nullable=False)
    pwd = db.Column(db.String(200), nullable=False)
    pts = db.Column(db.Integer, default=0)
    img = db.Column(db.String(200), default='default.jpg')
    bonus = db.Column(db.Boolean, default=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    memes = db.relationship('Meme', backref='user', lazy=True)

    def set_pwd(self, p):
        self.pwd = generate_password_hash(p)

    def check_pwd(self, p):
        return check_password_hash(self.pwd, p)


class Temp(db.Model):
    __tablename__ = 'temps'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    file = db.Column(db.String(200), nullable=False)
    prev = db.Column(db.String(200), nullable=False)
    cat = db.Column(db.String(50), default='classic')
    likes = db.Column(db.Integer, default=0)
    date = db.Column(db.DateTime, default=datetime.utcnow)


class Meme(db.Model):
    __tablename__ = 'memes'
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tid = db.Column(db.Integer, db.ForeignKey('temps.id'), nullable=False)
    top = db.Column(db.String(200), default='')
    bot = db.Column(db.String(200), default='')
    file = db.Column(db.String(200), nullable=False)
    likes = db.Column(db.Integer, default=0)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    tmp = db.relationship('Temp', backref='memes')


@lm.user_loader
def load_user(i):
    return User.query.get(int(i))


def make_meme(path, t, b, out):
    img = Image.open(path)
    if img.mode in ('RGBA', 'LA', 'P'):
        bg = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = bg
    d = ImageDraw.Draw(img)
    size = int(img.width / 12)
    fs = None
    for p in ["arial.ttf", "impact.ttf", "C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/arial.ttf"]:
        try:
            fs = ImageFont.truetype(p, size)
            break
        except:
            continue
    if fs is None:
        fs = ImageFont.load_default()
    if t:
        lines = textwrap.wrap(t.upper(), width=20)
        y = 10
        for line in lines:
            try:
                w = d.textbbox((0, 0), line, font=fs)[2] - d.textbbox((0, 0), line, font=fs)[0]
            except:
                w = len(line) * size // 2
            x = (img.width - w) / 2
            d.text((x, y), line, font=fs, fill='white', stroke_width=2, stroke_fill='black')
            y += size + 5
    if b:
        lines = textwrap.wrap(b.upper(), width=20)
        y = img.height - (len(lines) * (size + 5)) - 10
        for line in lines:
            try:
                w = d.textbbox((0, 0), line, font=fs)[2] - d.textbbox((0, 0), line, font=fs)[0]
            except:
                w = len(line) * size // 2
            x = (img.width - w) / 2
            d.text((x, y), line, font=fs, fill='white', stroke_width=2, stroke_fill='black')
            y += size + 5
    img.save(out, 'JPEG', quality=90)
    return out


ALLOWED = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED



class RegForm(FlaskForm):
    name = StringField('', validators=[DataRequired(), Length(min=3, max=80)])
    mail = StringField('', validators=[DataRequired()])
    pwd = PasswordField('', validators=[DataRequired(), Length(min=6)])
    pwd2 = PasswordField('', validators=[DataRequired(), EqualTo('pwd')])
    sub = SubmitField('OK')

    def validate_name(self, name):
        u = User.query.filter_by(name=name.data).first()
        if u:
            raise ValidationError('Занято')

    def validate_mail(self, mail):
        u = User.query.filter_by(mail=mail.data).first()
        if u:
            raise ValidationError('Занят')


class LoginForm(FlaskForm):
    name = StringField('', validators=[DataRequired()])
    pwd = PasswordField('', validators=[DataRequired()])
    sub = SubmitField('OK')


class ProfForm(FlaskForm):
    ava = FileField('')
    sub = SubmitField('OK')


class MemeForm(FlaskForm):
    tmp_id = SelectField('', coerce=int, validators=[DataRequired()])
    top = TextAreaField('')
    bot = TextAreaField('')
    tags = StringField('')
    sub = SubmitField('OK')

@app.route('/')
def index():
    r = Meme.query.order_by(db.func.random()).limit(6).all()
    p = Temp.query.order_by(Temp.likes.desc()).limit(6).all()
    return render_template('index.html', r=r, p=p)


@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    t = Temp.query.all()
    f = MemeForm()
    f.tmp_id.choices = [(x.id, x.name) for x in t]
    if f.validate_on_submit():
        tmp = Temp.query.get(f.tmp_id.data)
        p = os.path.join(app.config['TEMPLATE_FOLDER'], tmp.file)
        if not os.path.exists(p):
            flash('Нет файла', 'danger')
            return redirect(url_for('create'))
        name = f"meme_{current_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        out = os.path.join(app.config['GENERATED_FOLDER'], name)
        make_meme(p, f.top.data, f.bot.data, out)
        m = Meme(uid=current_user.id, tid=tmp.id, top=f.top.data, bot=f.bot.data, file=name)
        db.session.add(m)
        db.session.flush()
        add_tags(m.id, f.tags.data)
        db.session.commit()
        flash('Мем создан!', 'success')
        return redirect(url_for('gallery'))
    return render_template('create.html', f=f, t=t)


@app.route('/gallery')
def gallery():
    p = request.args.get('p', 1, type=int)
    m = Meme.query.order_by(Meme.date.desc()).paginate(page=p, per_page=12, error_out=False)
    return render_template('gallery.html', m=m)


@app.route('/meme/<int:id>')
def view_meme(id):
    m = Meme.query.get_or_404(id)
    mt = MemeTag.query.filter_by(mid=id).all()
    tags = [Tag.query.get(x.tid) for x in mt]
    is_fav = False
    if current_user.is_authenticated:
        is_fav = Fav.query.filter_by(uid=current_user.id, mid=id).first() is not None
    return render_template('view_meme.html', m=m, meme_tags=tags, is_fav=is_fav)


@app.route('/like/<int:id>')
@login_required
def like(id):
    m = Meme.query.get_or_404(id)
    m.likes += 1
    db.session.commit()
    flash('Лайк!', 'success')
    return redirect(url_for('view_meme', id=id))


@app.route('/like_t/<int:id>')
def like_t(id):
    t = Temp.query.get_or_404(id)
    t.likes += 1
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        n = request.form.get('name')
        c = request.form.get('cat', 'classic')
        f = request.files.get('img')
        if not n:
            flash('Введи название', 'danger')
            return redirect(url_for('add'))
        if f and allowed(f.filename):
            name = secure_filename(f"t_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{f.filename}")
            path = os.path.join(app.config['TEMPLATE_FOLDER'], name)
            f.save(path)
            t = Temp(name=n, file=name, prev=name, cat=c)
            db.session.add(t)
            db.session.commit()
            flash('Добавлено!', 'success')
            return redirect(url_for('create'))
        else:
            flash('Ошибка', 'danger')
    return render_template('add.html')

@app.route('/download/<name>')
def download(name):
    return send_file(os.path.join(app.config['GENERATED_FOLDER'], name), as_attachment=True)


@app.route('/api/rand')
def api_rand():
    m = Meme.query.order_by(db.func.random()).first()
    if m:
        return {'id': m.id, 'url': f"/static/generated/{m.file}", 'top': m.top, 'bot': m.bot, 'likes': m.likes}
    return {'error': 'no'}, 404


@app.route('/api/temps')
def api_temps():
    t = Temp.query.all()
    return [{'id': x.id, 'name': x.name, 'prev': f"/static/templates/{x.file}"} for x in t]


@app.route('/reg', methods=['GET', 'POST'])
def reg():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    f = RegForm()
    if f.validate_on_submit():
        u = User(name=f.name.data, mail=f.mail.data)
        u.set_pwd(f.pwd.data)
        db.session.add(u)
        db.session.commit()
        flash('Успешная регистрация!', 'success')
        return redirect(url_for('login'))
    return render_template('reg.html', f=f)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    f = LoginForm()
    if f.validate_on_submit():
        u = User.query.filter_by(name=f.name.data).first()
        if u and u.check_pwd(f.pwd.data):
            login_user(u)
            flash(f'Привет, {u.name}!', 'success')
            return redirect(url_for('index'))
        flash('Неверно', 'danger')
    return render_template('login.html', f=f)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Пока', 'info')
    return redirect(url_for('index'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    f = ProfForm()
    if f.validate_on_submit():
        if f.ava.data:
            file = f.ava.data
            if file and allowed(file.filename):
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                name = secure_filename(f"{current_user.id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], name))
                current_user.img = name
                db.session.commit()
                flash('Ава обновлена', 'success')
    um = Meme.query.filter_by(uid=current_user.id).order_by(Meme.date.desc()).all()
    return render_template('profile.html', f=f, um=um)


class ChangeForm(FlaskForm):
    o = PasswordField('', validators=[DataRequired()])
    n = PasswordField('', validators=[DataRequired(), Length(min=6)])
    n2 = PasswordField('', validators=[DataRequired(), EqualTo('n')])
    sub = SubmitField('OK')


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    f = ChangeForm()
    if f.validate_on_submit():
        if current_user.check_pwd(f.o.data):
            current_user.set_pwd(f.n.data)
            db.session.commit()
            flash('Пароль изменён!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Неверный пароль', 'danger')
    return render_template('settings.html', f=f)


@app.route('/change_name', methods=['POST'])
@login_required
def change_name():
    nn = request.form.get('nn')
    if nn and len(nn) >= 3:
        ex = User.query.filter_by(name=nn).first()
        if ex:
            flash('Имя занято', 'danger')
        else:
            current_user.name = nn
            db.session.commit()
            flash('Имя изменено!', 'success')
    else:
        flash('Минимум 3 символа', 'danger')
    return redirect(url_for('profile'))


@app.route('/delete/<int:id>')
@login_required
def delete(id):
    m = Meme.query.get_or_404(id)
    if m.uid != current_user.id:
        flash('Не твой мем!', 'danger')
        return redirect(url_for('gallery'))
    p = os.path.join(app.config['GENERATED_FOLDER'], m.file)
    if os.path.exists(p):
        os.remove(p)
    db.session.delete(m)
    db.session.commit()
    flash('Мем удалён', 'success')
    return redirect(url_for('profile'))

class Fav(db.Model):
    __tablename__ = 'favs'
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.Integer, db.ForeignKey('users.id'))
    mid = db.Column(db.Integer, db.ForeignKey('memes.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)

class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)

class MemeTag(db.Model):
    __tablename__ = 'meme_tags'
    id = db.Column(db.Integer, primary_key=True)
    mid = db.Column(db.Integer, db.ForeignKey('memes.id'))
    tid = db.Column(db.Integer, db.ForeignKey('tags.id'))


@app.route('/fav/<int:mid>')
@login_required
def fav(mid):
    ex = Fav.query.filter_by(uid=current_user.id, mid=mid).first()
    if ex:
        db.session.delete(ex)
        flash('Удалено из избранного', 'info')
    else:
        f = Fav(uid=current_user.id, mid=mid)
        db.session.add(f)
        flash('Добавлено в избранное', 'success')
    db.session.commit()
    return redirect(url_for('view_meme', id=mid))

@app.route('/favorites')
@login_required
def favorites():
    f = Fav.query.filter_by(uid=current_user.id).order_by(Fav.date.desc()).all()
    memes = [Meme.query.get(x.mid) for x in f if Meme.query.get(x.mid)]
    return render_template('favorites.html', memes=memes)


def add_tags(mid, tags_str):
    if not tags_str:
        return
    for name in tags_str.lower().split():
        name = name.strip('#,.;!?')
        if name and len(name) <= 30:
            tag = Tag.query.filter_by(name=name).first()
            if not tag:
                tag = Tag(name=name)
                db.session.add(tag)
                db.session.flush()
            ex = MemeTag.query.filter_by(mid=mid, tid=tag.id).first()
            if not ex:
                mt = MemeTag(mid=mid, tid=tag.id)
                db.session.add(mt)

@app.route('/tag/<string:name>')
def tag(name):
    tag = Tag.query.filter_by(name=name.lower()).first()
    if not tag:
        flash('Тег не найден', 'danger')
        return redirect(url_for('index'))
    mt = MemeTag.query.filter_by(tid=tag.id).all()
    memes = [Meme.query.get(x.mid) for x in mt if Meme.query.get(x.mid)]
    return render_template('tag.html', memes=memes, tag=name)

@app.route('/tags')
def tags():
    popular = db.session.query(Tag.name, db.func.count(MemeTag.mid)).join(MemeTag).group_by(Tag.id).order_by(db.func.count(MemeTag.mid).desc()).limit(30).all()
    return render_template('tags.html', tags=popular)


def make_backup():
    d = datetime.now().strftime('%Y%m%d_%H%M%S')
    folder = f'backups/bk_{d}'
    os.makedirs(folder, exist_ok=True)
    db_files = glob.glob('**/memgen.db', recursive=True)
    if db_files:
        db_path = db_files[0]
        shutil.copy2(db_path, os.path.join(folder, 'db.db'))
        print(f"[BACKUP] БД скопирована из {db_path}")
    else:
        print("[BACKUP] БД не найдена!")
        return False
    for src, dst in [('static/generated', 'generated'),
                     ('static/uploads', 'uploads'),
                     ('static/templates', 'templates')]:
        if os.path.exists(src):
            shutil.copytree(src, os.path.join(folder, dst))
            print(f"[BACKUP] {dst} скопирована")
    return True


@app.route('/backup')
@login_required
def backup():
    try:
        make_backup()
        flash('Бэкап создан!', 'success')
    except Exception as e:
        flash(f'Ошибка: {e}', 'danger')
    return redirect(url_for('backups'))


@app.route('/restore/<name>')
@login_required
def restore(name):
    src = os.path.join('backups', name)
    if not os.path.exists(src):
        flash('Бэкап не найден', 'danger')
        return redirect(url_for('backups'))
    try:
        db_src = os.path.join(src, 'db.db')
        if os.path.exists(db_src):
            shutil.copy2(db_src, 'var/app-instance/memgen.db')
            print(f"[RESTORE] БД восстановлена в var/app-instance/memgen.db")
        for f in ['generated', 'uploads', 'templates']:
            src_f = os.path.join(src, f)
            dst_f = os.path.join('static', f)
            if os.path.exists(src_f):
                if os.path.exists(dst_f):
                    shutil.rmtree(dst_f)
                shutil.copytree(src_f, dst_f)
                print(f"[RESTORE] {f} восстановлен")

        flash(' Восстановлено!', 'success')
    except Exception as e:
        print(f"[RESTORE] Ошибка: {e}")
        flash(f'Ошибка: {e}', 'danger')
    return redirect(url_for('backups'))


@app.route('/backups')
@login_required
def backups():
    items = []
    if os.path.exists('backups'):
        items = sorted([f for f in os.listdir('backups') if f.startswith('bk_')], reverse=True)
    return render_template('backups.html', backups=items)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        fold = app.config['TEMPLATE_FOLDER']
        my_files = ['drake.jpg', 'drake.png', 'bob.jpg', 'money.jpg', 'ruk.jpg']
        if os.path.exists(fold):
            for f in os.listdir(fold):
                if f in my_files:
                    ex = Temp.query.filter_by(file=f).first()
                    if not ex:
                        try:
                            path = os.path.join(fold, f)
                            n = os.path.splitext(f)[0].replace('_', ' ').title()
                            t = Temp(name=n, file=f, prev=f, cat='classic')
                            db.session.add(t)
                            print(f" Добавлен: {n} ({f})")
                        except Exception as e:
                            print(f" Ошибка с {f}: {e}")
            db.session.commit()
            print(f"Всего шаблонов: {Temp.query.count()}")

    app.run(debug=True)
