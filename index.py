import telebot
from telebot import types
import sqlite3
import time
import random
import logging
from datetime import datetime
import requests
import json

# Bot tokeni
TOKEN = '7811273850:AAHV2sFN6FqauHKmYIHHfIeMhaiLdL6oPsU'
WEBSITE_URL = 'https://yoshekologlar.vercel.app'

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN, threaded=True)

# ==================== MA'LUMOTLAR BAZASI ====================
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('yosh_ekologlar.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
        logger.info("✅ Database yaratildi")
    
    def create_tables(self):
        self.cursor.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                language TEXT DEFAULT 'uz',
                registered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP,
                total_score INTEGER DEFAULT 0,
                quizzes_completed INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                games_won INTEGER DEFAULT 0,
                eco_points INTEGER DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS quiz_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question TEXT,
                user_answer TEXT,
                correct_answer TEXT,
                is_correct BOOLEAN,
                points INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            );
            
            CREATE TABLE IF NOT EXISTS daily_facts_sent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date DATE,
                UNIQUE(user_id, date)
            );
            
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                achievement_name TEXT,
                earned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            );
        ''')
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name, last_name=None, language='uz'):
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, last_name, language, last_activity)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, language, datetime.now()))
            self.conn.commit()
            logger.info(f"✅ Yangi foydalanuvchi: {first_name} (ID: {user_id})")
        except Exception as e:
            logger.error(f"❌ User qo'shishda xatolik: {e}")
    
    def update_language(self, user_id, language):
        self.cursor.execute('UPDATE users SET language = ? WHERE user_id = ?', (language, user_id))
        self.conn.commit()
    
    def get_language(self, user_id):
        try:
            self.cursor.execute('SELECT language FROM users WHERE user_id = ?', (user_id,))
            result = self.cursor.fetchone()
            return result[0] if result else 'uz'
        except:
            return 'uz'
    
    def update_activity(self, user_id):
        self.cursor.execute('UPDATE users SET last_activity = ? WHERE user_id = ?', 
                          (datetime.now(), user_id))
        self.conn.commit()
    
    def add_score(self, user_id, points):
        self.cursor.execute('UPDATE users SET total_score = total_score + ? WHERE user_id = ?', 
                          (points, user_id))
        self.conn.commit()
    
    def add_eco_points(self, user_id, points):
        self.cursor.execute('UPDATE users SET eco_points = eco_points + ? WHERE user_id = ?', 
                          (points, user_id))
        self.conn.commit()
    
    def record_quiz(self, user_id, question, user_answer, correct_answer, is_correct, points):
        try:
            self.cursor.execute('''
                INSERT INTO quiz_results 
                (user_id, question, user_answer, correct_answer, is_correct, points)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, question, user_answer, correct_answer, is_correct, points))
            
            if is_correct:
                self.cursor.execute('''
                    UPDATE users 
                    SET quizzes_completed = quizzes_completed + 1,
                        correct_answers = correct_answers + 1
                    WHERE user_id = ?
                ''', (user_id,))
            else:
                self.cursor.execute('''
                    UPDATE users SET quizzes_completed = quizzes_completed + 1
                    WHERE user_id = ?
                ''', (user_id,))
            
            self.conn.commit()
        except Exception as e:
            logger.error(f"❌ Quiz yozishda xatolik: {e}")
    
    def record_game(self, user_id, game_name, score, level):
        try:
            self.cursor.execute('''
                INSERT INTO game_results (user_id, game_name, score, level)
                VALUES (?, ?, ?, ?)
            ''', (user_id, game_name, score, level))
            
            self.cursor.execute('''
                UPDATE users 
                SET games_played = games_played + 1,
                    games_won = games_won + ?
                WHERE user_id = ?
            ''', (1 if score > 50 else 0, user_id))
            self.conn.commit()
        except:
            pass  # Game results table might not exist
    
    def get_user_stats(self, user_id):
        try:
            self.cursor.execute('''
                SELECT total_score, quizzes_completed, correct_answers, 
                       games_played, games_won, eco_points
                FROM users WHERE user_id = ?
            ''', (user_id,))
            return self.cursor.fetchone()
        except:
            return (0, 0, 0, 0, 0, 0)
    
    def get_leaderboard(self, limit=10):
        try:
            self.cursor.execute('''
                SELECT first_name, username, total_score, correct_answers, eco_points
                FROM users 
                ORDER BY total_score DESC, eco_points DESC
                LIMIT ?
            ''', (limit,))
            return self.cursor.fetchall()
        except:
            return []
    
    def check_achievement(self, user_id, achievement_name):
        self.cursor.execute('''
            SELECT * FROM achievements 
            WHERE user_id = ? AND achievement_name = ?
        ''', (user_id, achievement_name))
        return self.cursor.fetchone() is None
    
    def add_achievement(self, user_id, achievement_name):
        if self.check_achievement(user_id, achievement_name):
            self.cursor.execute('''
                INSERT INTO achievements (user_id, achievement_name)
                VALUES (?, ?)
            ''', (user_id, achievement_name))
            self.conn.commit()
            return True
        return False

db = Database()

# ==================== TARJIMALAR ====================
TRANSLATIONS = {
    'uz': {
        'welcome': 'Assalomu alaykum, <b>{name}</b>! 👋\n\n🌱 <b>Yosh Ekologlar</b> botiga xush kelibsiz!\n\n📊 <b>Statistika:</b>\n• 25 ta ekologik test\n• 3 ta interaktiv o\'yin\n• Kunlik faktlar\n• Challenge\'lar\n• Reyting tizimi\n\n🌐 Saytimiz: yoshekologlar.vercel.app\n\nBoshlash uchun menyudan tanlang! 👇',
        'select_language': '🌍 <b>Tilni tanlang</b> / <b>Select Language</b>:',
        'language_changed': '✅ Til o\'zgartirildi: {lang}',
        'eco_question': '🌿 <b>EKOLOGIK SAVOL</b>\n\nMenga ekologiya bo\'yicha savolingizni yozing.\n\n💡 <b>Misol:</b>\n• Global isish nima?\n• Plastik qancha vaqtda chiriydi?\n• Suvni qanday tejash mumkin?\n• Daraxtlar nima uchun muhim?',
        'test_menu': '📝 <b>EKOLOGIK TESTLAR</b>\n\n📊 <b>Ma\'lumot:</b>\n• Jami: 25 ta savol\n• Har biri: 10-20 ball\n• Murakkablik: Oson → Qiyin\n\n🎯 Testni boshlash uchun quyidagi tugmani bosing!',
        'game_menu': '🎮 <b>EKO O\'YINLAR</b>\n\n🎯 <b>Mavjud o\'yinlar:</b>\n\n1️⃣ ♻️ Chiqindilarni saralash\n   • 10 ta savol\n   • Har biri 10 ball\n\n2️⃣  Daraxt ekish\n   • 10 daraxt eking\n   • 100 ball\n\n3️⃣  Suvni tejash\n   • 5 ta vaziyat\n   • 20 ball har biri\n\nTanlang:',
        'stats': '📊 <b>SIZNING STATISTIKANGIZ</b>\n\n🏆 Jami ball: {score}\n🌱 Eco points: {eco_points}\n📝 Testlar: {quizzes}\n✅ To\'g\'ri javoblar: {correct}\n🎮 O\'yinlar: {games_played}\n🏆 Yutilgan o\'yinlar: {games_won}\n📈 Muaffaqiyat: {accuracy}%',
        'leaderboard': '🏆 <b>ENG YAXSHI EKOLOGLAR</b>\n\n',
        'daily_fact': '📰 <b>KUNLIK EKO FAKT</b>\n\n{fact}\n\n<i>Ertaga yana keling!</i>',
        'challenges': '🎯 <b>EKO CHALLENGE\'LAR</b>\n\nChallenge\'larni bajaring va katta mukofotlar qo\'lga kiriting!\n\n',
        'contact': '📞 <b>BOG\'LANISH</b>\n\n📧 Email: info@yosh-ekologlar.uz\n🌐 Sayt: yoshekologlar.vercel.app\n📱 Telegram: @yoshekologlar\n\n💬 Savollaringiz bo\'lsa, yozing!',
        'help': 'ℹ️ <b>YORDAM</b>\n\n📋 <b>Asosiy komandalar:</b>\n/start - Botni qayta boshlash\n/lang - Tilni o\'zgartirish\n/stats - Statistika\n/test - Test boshlash\n/game - O\'yinlar\n/fact - Kunlik fakt\n/help - Yordam\n\n💡 Har qanday savol bo\'lsa, /contact',
        'commands': '📋 <b>BARCHA KOMANDALAR</b>\n\n/start - Botni boshlash\n/lang - Tilni o\'zgartirish\n/stats - Statistika\n/test - Test boshlash\n/game - O\'yinlar\n/fact - Kunlik fakt\n/eco_questions - Ekologik savollar\n/challenges - Challenge\'lar\n/leaderboard - Reyting\n/help - Yordam\n/contact - Bog\'lanish',
        'correct_answer': '✅ <b>TO\'G\'RI JAVOB!</b>\n\n{info}\n\n🏆 +{points} ball!\n📊 Jami: {total_score} ball',
        'wrong_answer': '❌ <b>NOTO\'G\'RI JAVOB</b>\n\n✅ To\'g\'ri javob: {correct}\n\n📚 {info}',
        'game_won': '🎉 <b>G\'ALABA!</b>\n\nSiz ajoyib natija ko\'rsatdingiz!\n\n🏆 +{points} ball\n🌱 +{eco_points} eco points',
        'game_lost': '😔 <b>YUTQAZDINGIZ</b>\n\nKeyingi safar omadli bo\'ladi!\n\n💪 Mashq qilishda davom eting!',
        'continue': '🔄 Davom etamizmi?',
        'back': '🔙 Orqaga',
        'start_game': '🎮 O\'yinni boshlash',
        'new_test': '🔄 Yangi test',
        'main_menu': '🏠 Bosh menyu',
        'website': '🌐 <b>BIZNING SAYT</b>\n\n🚀 yoshekologlar.vercel.app\n\n✨ 3D o\'rmon dunyosi\n🎮 Interaktiv o\'yinlar\n📊 Real-time statistika\n🌱 Eco challenge\'lar\n🏆 Global reyting\n\nSaytga o\'tish uchun quyidagi tugmani bosing! 👇',
        'achievement': '🏆 <b>YANGI YUTUQ!</b>\n\nSiz "{achievement}" yutug\'iga erishdingiz!\n\n🌟 Davom eting!'
    },
    'ru': {
        'welcome': 'Здравствуйте, <b>{name}</b>! 👋\n\n🌱 Добро пожаловать в <b>Юные Экологи</b>!\n\n📊 <b>Возможности:</b>\n• 25 экологических тестов\n• 3 интерактивные игры\n• Факты дня\n• Испытания\n• Рейтинговая система\n\n🌐 Сайт: yoshekologlar.vercel.app\n\nВыберите из меню! 👇',
        'select_language': '🌍 <b>Выберите язык</b> / <b>Select Language</b>:',
        'language_changed': '✅ Язык изменен: {lang}',
        'eco_question': '🌿 <b>ЭКОЛОГИЧЕСКИЙ ВОПРОС</b>\n\nНапишите ваш вопрос по экологии.\n\n💡 <b>Примеры:</b>\n• Что такое глобальное потепление?\n• Сколько разлагается пластик?\n• Как экономить воду?',
        'test_menu': '📝 <b>ЭКОЛОГИЧЕСКИЕ ТЕСТЫ</b>\n\n📊 <b>Информация:</b>\n• Всего: 25 вопросов\n• Каждый: 10-20 баллов\n• Сложность: Легко → Сложно\n\nНажмите кнопку чтобы начать!',
        'game_menu': '🎮 <b>ЭКО ИГРЫ</b>\n\n🎯 <b>Доступные игры:</b>\n\n1️⃣ ♻️ Сортировка отходов\n   • 10 вопросов\n   • 10 баллов каждый\n\n2️⃣  Посадка деревьев\n   • Посадите 10 деревьев\n   • 100 баллов\n\n3️⃣ 💧 Экономия воды\n   • 5 ситуаций\n   • 20 баллов каждый\n\nВыберите:',
        'stats': '📊 <b>ВАША СТАТИСТИКА</b>\n\n🏆 Всего баллов: {score}\n🌱 Eco points: {eco_points}\n📝 Тесты: {quizzes}\n✅ Правильно: {correct}\n🎮 Игры: {games_played}\n🏆 Выиграно: {games_won}\n📈 Успешность: {accuracy}%',
        'leaderboard': '🏆 <b>ЛУЧШИЕ ЭКОЛОГИ</b>\n\n',
        'daily_fact': '📰 <b>ФАКТ ДНЯ</b>\n\n{fact}\n\n<i>Приходите завтра!</i>',
        'challenges': '🎯 <b>ЭКО ИСПЫТАНИЯ</b>\n\nВыполняйте и получайте награды!\n\n',
        'contact': '📞 <b>КОНТАКТЫ</b>\n\n📧 Email: info@yosh-ekologlar.uz\n🌐 Сайт: yoshekologlar.vercel.app\n📱 Telegram: @yoshekologlar\n\n💬 Пишите если есть вопросы!',
        'help': 'ℹ️ <b>ПОМОЩЬ</b>\n\n📋 <b>Основные команды:</b>\n/start - Перезапустить бота\n/lang - Сменить язык\n/stats - Статистика\n/test - Начать тест\n/game - Игры\n/fact - Факт дня\n/help - Помощь\n\n💡 Любые вопросы? /contact',
        'commands': '📋 <b>ВСЕ КОМАНДЫ</b>\n\n/start - Запустить\n/lang - Сменить язык\n/stats - Статистика\n/test - Тест\n/game - Игры\n/fact - Факт дня\n/eco_questions - Вопросы\n/challenges - Испытания\n/leaderboard - Рейтинг\n/help - Помощь\n/contact - Контакты',
        'correct_answer': '✅ <b>ПРАВИЛЬНО!</b>\n\n{info}\n\n🏆 +{points} баллов!\n📊 Всего: {total_score} баллов',
        'wrong_answer': '❌ <b>НЕПРАВИЛЬНО</b>\n\n✅ Правильный ответ: {correct}\n\n📚 {info}',
        'game_won': '🎉 <b>ПОБЕДА!</b>\n\nОтличный результат!\n\n🏆 +{points} баллов\n🌱 +{eco_points} eco points',
        'game_lost': '😔 <b>ПРОИГРЫШ</b>\n\nВ следующий раз повезет!\n\n💪 Продолжайте практиковаться!',
        'continue': '🔄 Продолжить?',
        'back': '🔙 Назад',
        'start_game': '🎮 Начать игру',
        'new_test': '🔄 Новый тест',
        'main_menu': '🏠 Главное меню',
        'website': '🌐 <b>НАШ САЙТ</b>\n\n🚀 yoshekologlar.vercel.app\n\n✨ 3D мир леса\n🎮 Интерактивные игры\n📊 Статистика в реальном времени\n🌱 Eco испытания\n🏆 Глобальный рейтинг\n\nНажмите кнопку чтобы перейти! 👇',
        'achievement': '🏆 <b>НОВОЕ ДОСТИЖЕНИЕ!</b>\n\nВы получили "{achievement}"!\n\n🌟 Так держать!'
    },
    'en': {
        'welcome': 'Hello, <b>{name}</b>! 👋\n\n🌱 Welcome to <b>Young Ecologists</b>!\n\n📊 <b>Features:</b>\n• 25 ecology tests\n• 3 interactive games\n• Daily facts\n• Challenges\n• Rating system\n\n🌐 Website: yoshekologlar.vercel.app\n\nChoose from menu! 👇',
        'select_language': '🌍 <b>Select Language</b> / <b>Tilni tanlang</b>:',
        'language_changed': '✅ Language changed: {lang}',
        'eco_question': '🌿 <b>ECOLOGY QUESTION</b>\n\nWrite your ecology question.\n\n💡 <b>Examples:</b>\n• What is global warming?\n• How long does plastic decompose?\n• How to save water?',
        'test_menu': '📝 <b>ECOLOGY TESTS</b>\n\n📊 <b>Info:</b>\n• Total: 25 questions\n• Each: 10-20 points\n• Difficulty: Easy → Hard\n\nPress button to start!',
        'game_menu': '🎮 <b>ECO GAMES</b>\n\n🎯 <b>Available games:</b>\n\n1️⃣ ♻️ Waste Sorting\n   • 10 questions\n   • 10 points each\n\n2️⃣ 🌱 Tree Planting\n   • Plant 10 trees\n   • 100 points\n\n3️⃣ 💧 Water Saving\n   • 5 scenarios\n   • 20 points each\n\nChoose:',
        'stats': '📊 <b>YOUR STATISTICS</b>\n\n🏆 Total points: {score}\n🌱 Eco points: {eco_points}\n📝 Tests: {quizzes}\n✅ Correct: {correct}\n🎮 Games: {games_played}\n🏆 Won: {games_won}\n📈 Success: {accuracy}%',
        'leaderboard': '🏆 <b>BEST ECOLOGISTS</b>\n\n',
        'daily_fact': '📰 <b>DAILY FACT</b>\n\n{fact}\n\n<i>Come back tomorrow!</i>',
        'challenges': '🎯 <b>ECO CHALLENGES</b>\n\nComplete and earn rewards!\n\n',
        'contact': '📞 <b>CONTACT</b>\n\n📧 Email: info@yosh-ekologlar.uz\n🌐 Website: yoshekologlar.vercel.app\n📱 Telegram: @yoshekologlar\n\n💬 Write if you have questions!',
        'help': 'ℹ️ <b>HELP</b>\n\n📋 <b>Main commands:</b>\n/start - Restart bot\n/lang - Change language\n/stats - Statistics\n/test - Start test\n/game - Games\n/fact - Daily fact\n/help - Help\n\n💡 Any questions? /contact',
        'commands': '📋 <b>ALL COMMANDS</b>\n\n/start - Start\n/lang - Change language\n/stats - Statistics\n/test - Test\n/game - Games\n/fact - Daily fact\n/eco_questions - Questions\n/challenges - Challenges\n/leaderboard - Rating\n/help - Help\n/contact - Contact',
        'correct_answer': '✅ <b>CORRECT!</b>\n\n{info}\n\n🏆 +{points} points!\n📊 Total: {total_score} points',
        'wrong_answer': '❌ <b>WRONG</b>\n\n✅ Correct answer: {correct}\n\n📚 {info}',
        'game_won': '🎉 <b>VICTORY!</b>\n\nGreat result!\n\n🏆 +{points} points\n🌱 +{eco_points} eco points',
        'game_lost': '😔 <b>LOSS</b>\n\nBetter luck next time!\n\n💪 Keep practicing!',
        'continue': '🔄 Continue?',
        'back': '🔙 Back',
        'start_game': '🎮 Start Game',
        'new_test': '🔄 New Test',
        'main_menu': '🏠 Main Menu',
        'website': '🌐 <b>OUR WEBSITE</b>\n\n🚀 yoshekologlar.vercel.app\n\n✨ 3D forest world\n🎮 Interactive games\n📊 Real-time statistics\n🌱 Eco challenges\n🏆 Global rating\n\nPress button to visit! 👇',
        'achievement': '🏆 <b>NEW ACHIEVEMENT!</b>\n\nYou earned "{achievement}"!\n\n🌟 Keep going!'
    }
}

# ==================== 25 TA TEST SAVOLLARI ====================
QUIZ_QUESTIONS = [
    {
        'q_uz': '🌱 Bir daraxt kuniga qancha kislorod ishlab chiqaradi?',
        'q_ru': '🌱 Сколько кислорода производит дерево в день?',
        'q_en': '🌱 How much oxygen does a tree produce per day?',
        'options': ['A) 10 kishiga', 'B) 100 kishiga ✅', 'C) 1000 kishiga'],
        'options_ru': ['A) 10 людям', 'B) 100 людям ✅', 'C) 1000 людям'],
        'options_en': ['A) 10 people', 'B) 100 people ✅', 'C) 1000 people'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Katta daraxt kuniga 100 kishiga yetadigan kislorod ishlab chiqaradi!',
        'info_ru': 'Правильно! Большое дерево производит кислород для 100 человек!',
        'info_en': 'Correct! A large tree produces oxygen for 100 people!',
        'points': 10
    },
    {
        'q_uz': '♻️ Plastik shisha qancha vaqtda chiriydi?',
        'q_ru': '♻️ Сколько времени разлагается пластиковая бутылка?',
        'q_en': '♻️ How long does a plastic bottle take to decompose?',
        'options': ['A) 50-100 yil', 'B) 100-450 yil ✅', 'C) 10-20 yil'],
        'options_ru': ['A) 50-100 лет', 'B) 100-450 лет ✅', 'C) 10-20 лет'],
        'options_en': ['A) 50-100 years', 'B) 100-450 years ✅', 'C) 10-20 years'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Plastik 100-450 yil davomida tabiatda saqlanadi.',
        'info_ru': 'Правильно! Пластик сохраняется 100-450 лет!',
        'info_en': 'Correct! Plastic remains for 100-450 years!',
        'points': 10
    },
    {
        'q_uz': '💧 Yer yuzidagi chuchuk suvning necha foizi ichishga yaroqli?',
        'q_ru': '💧 Какой процент пресной воды пригоден для питья?',
        'q_en': '💧 What percentage of freshwater is drinkable?',
        'options': ['A) 10%', 'B) 5%', 'C) 1% dan kam ✅'],
        'options_ru': ['A) 10%', 'B) 5%', 'C) Менее 1% ✅'],
        'options_en': ['A) 10%', 'B) 5%', 'C) Less than 1% ✅'],
        'correct': 'C',
        'info_uz': 'Afsuski to\'g\'ri! Chuchuk suvning 1% dan kam qismi ichishga yaroqli.',
        'info_ru': 'К сожалению верно! Менее 1% пресной воды пригодна.',
        'info_en': 'Unfortunately correct! Less than 1% is drinkable.',
        'points': 15
    },
    {
        'q_uz': '🌍 Atmosferada eng ko\'p uchraydigan gaz qaysi?',
        'q_ru': '🌍 Какой газ наиболее распространен в атмосфере?',
        'q_en': '🌍 What is the most common gas in the atmosphere?',
        'options': ['A) Kislorod', 'B) Azot ✅', 'C) Karbonat angidrid'],
        'options_ru': ['A) Кислород', 'B) Азот ✅', 'C) Углекислый газ'],
        'options_en': ['A) Oxygen', 'B) Nitrogen ✅', 'C) Carbon dioxide'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Azot atmosferaning 78% ni tashkil qiladi.',
        'info_ru': 'Правильно! Азот составляет 78% атмосферы.',
        'info_en': 'Correct! Nitrogen makes up 78% of the atmosphere.',
        'points': 10
    },
    {
        'q_uz': '🔋 Quyosh energiyasi qaysi turdagi energiya?',
        'q_ru': '🔋 Какой тип энергии представляет солнечная энергия?',
        'q_en': '🔋 What type of energy is solar energy?',
        'options': ['A) Qayta tiklanadigan ✅', 'B) Qayta tiklanmaydigan', 'C) Yadro energiyasi'],
        'options_ru': ['A) Возобновляемая ✅', 'B) Невозобновляемая', 'C) Ядерная'],
        'options_en': ['A) Renewable ✅', 'B) Non-renewable', 'C) Nuclear'],
        'correct': 'A',
        'info_uz': 'Ajoyib! Quyosh energiyasi - toza va qayta tiklanadigan!',
        'info_ru': 'Отлично! Солнечная энергия - чистая и возобновляемая!',
        'info_en': 'Excellent! Solar energy is clean and renewable!',
        'points': 10
    },
    {
        'q_uz': '🚮 Bir kishi o\'rtacha kuniga qancha chiqindi chiqaradi?',
        'q_ru': '🚮 Сколько отходов производит человек в день?',
        'q_en': '🚮 How much waste does a person produce per day?',
        'options': ['A) 0.5-1 kg ✅', 'B) 5-10 kg', 'C) 20-30 kg'],
        'options_ru': ['A) 0.5-1 кг ✅', 'B) 5-10 кг', 'C) 20-30 кг'],
        'options_en': ['A) 0.5-1 kg ✅', 'B) 5-10 kg', 'C) 20-30 kg'],
        'correct': 'A',
        'info_uz': 'To\'g\'ri! Har birimiz kuniga 0.5-1 kg chiqindi chiqaramiz.',
        'info_ru': 'Правильно! Каждый производит 0.5-1 кг отходов в день.',
        'info_en': 'Correct! Each person produces 0.5-1 kg daily.',
        'points': 15
    },
    {
        'q_uz': '🌊 Dunyo okeanlari Yer yuzining necha foizini egallaydi?',
        'q_ru': '🌊 Какой процент Земли занимают океаны?',
        'q_en': '🌊 What percentage of Earth is covered by oceans?',
        'options': ['A) 51%', 'B) 71% ✅', 'C) 91%'],
        'options_ru': ['A) 51%', 'B) 71% ✅', 'C) 91%'],
        'options_en': ['A) 51%', 'B) 71% ✅', 'C) 91%'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Okeanlar Yer yuzining 71% ni qoplaydi!',
        'info_ru': 'Правильно! Океаны покрывают 71% Земли!',
        'info_en': 'Correct! Oceans cover 71% of Earth!',
        'points': 10
    },
    {
        'q_uz': '🌡️ Global isish natijasida dengiz sathi qancha ko\'tarilishi mumkin?',
        'q_ru': '🌡️ Насколько поднимется уровень моря?',
        'q_en': '🌡️ How much can sea level rise?',
        'options': ['A) 1-2 metr', 'B) 0.3-1 metr ✅', 'C) 5-10 metr'],
        'options_ru': ['A) 1-2 метра', 'B) 0.3-1 метра ✅', 'C) 5-10 метров'],
        'options_en': ['A) 1-2 meters', 'B) 0.3-1 meters ✅', 'C) 5-10 meters'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! 2100-yilgacha 0.3-1 metr ko\'tarilishi mumkin.',
        'info_ru': 'Правильно! К 2100 году на 0.3-1 метра.',
        'info_en': 'Correct! Could rise 0.3-1 meters by 2100.',
        'points': 20
    },
    {
        'q_uz': '🐼 Qaysi hayvon yo\'qolib borayotgan turlar ro\'yxatida?',
        'q_ru': '🐼 Какое животное под угрозой исчезновения?',
        'q_en': '🐼 Which animal is endangered?',
        'options': ['A) Mushuk', 'B) Panda ✅', 'C) It'],
        'options_ru': ['A) Кошка', 'B) Панда ✅', 'C) Собака'],
        'options_en': ['A) Cat', 'B) Panda ✅', 'C) Dog'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Pandalar yo\'qolib borayotgan turlar qatorida.',
        'info_ru': 'Правильно! Панды под угрозой исчезновения.',
        'info_en': 'Correct! Pandas are endangered.',
        'points': 10
    },
    {
        'q_uz': '♻️ Alyuminiy qancha marta qayta ishlanishi mumkin?',
        'q_ru': '♻️ Сколько раз можно перерабатывать алюминий?',
        'q_en': '♻️ How many times can aluminum be recycled?',
        'options': ['A) 1 marta', 'B) 5 marta', 'C) Cheksiz ✅'],
        'options_ru': ['A) 1 раз', 'B) 5 раз', 'C) Бесконечно ✅'],
        'options_en': ['A) 1 time', 'B) 5 times', 'C) Infinitely ✅'],
        'correct': 'C',
        'info_uz': 'Ajoyib! Alyuminiy cheksiz marta qayta ishlanishi mumkin!',
        'info_ru': 'Отлично! Алюминий можно перерабатывать бесконечно!',
        'info_en': 'Excellent! Aluminum can be recycled infinitely!',
        'points': 15
    },
    {
        'q_uz': '🌳 O\'zbekistonda qaysi daraxt eng ko\'p ekilgan?',
        'q_ru': '🌳 Какое дерево наиболее распространено в Узбекистане?',
        'q_en': '🌳 Which tree is most common in Uzbekistan?',
        'options': ['A) Olma', 'B) Terak ✅', 'C) Zarang'],
        'options_ru': ['A) Яблоня', 'B) Тополь ✅', 'C) Клен'],
        'options_en': ['A) Apple', 'B) Poplar ✅', 'C) Maple'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Terak - O\'zbekistonda eng keng tarqalgan!',
        'info_ru': 'Правильно! Тополь самое распространенное!',
        'info_en': 'Correct! Poplar is most common!',
        'points': 10
    },
    {
        'q_uz': '💡 LED lampa oddiy lampaga qaraganda qancha energiya tejaydi?',
        'q_ru': '💡 Сколько энергии экономит LED лампа?',
        'q_en': '💡 How much energy does LED save?',
        'options': ['A) 20-30%', 'B) 80-90% ✅', 'C) 50%'],
        'options_ru': ['A) 20-30%', 'B) 80-90% ✅', 'C) 50%'],
        'options_en': ['A) 20-30%', 'B) 80-90% ✅', 'C) 50%'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! LED lampalar 80-90% gacha energiya tejaydi!',
        'info_ru': 'Правильно! LED экономят 80-90% энергии!',
        'info_en': 'Correct! LEDs save 80-90% energy!',
        'points': 15
    },
    {
        'q_uz': '🌾 Organik dehqonchilikda nima ishlatilmaydi?',
        'q_ru': '🌾 Что не используется в органическом земледелии?',
        'q_en': '🌾 What is not used in organic farming?',
        'options': ['A) Tabiiy o\'g\'itlar', 'B) Kimyoviy pestitsidlar ✅', 'C) Kompost'],
        'options_ru': ['A) Натуральные удобрения', 'B) Химические пестициды ✅', 'C) Компост'],
        'options_en': ['A) Natural fertilizers', 'B) Chemical pesticides ✅', 'C) Compost'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Organik dehqonchilikda kimyoviy moddalar ishlatilmaydi!',
        'info_ru': 'Правильно! В органическом не используются химикаты!',
        'info_en': 'Correct! Organic farming doesn\'t use chemicals!',
        'points': 15
    },
    {
        'q_uz': '🚰 Bir daqiqada ochiq krandan qancha suv oqib chiqadi?',
        'q_ru': '🚰 Сколько воды вытекает из крана за минуту?',
        'q_en': '🚰 How much water flows from tap per minute?',
        'options': ['A) 1-2 litr', 'B) 6-10 litr ✅', 'C) 20-30 litr'],
        'options_ru': ['A) 1-2 литра', 'B) 6-10 литров ✅', 'C) 20-30 литров'],
        'options_en': ['A) 1-2 liters', 'B) 6-10 liters ✅', 'C) 20-30 liters'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Shuning uchun kranni yopish juda muhim!',
        'info_ru': 'Правильно! Поэтому важно закрывать кран!',
        'info_en': 'Correct! That\'s why closing tap is important!',
        'points': 10
    },
    {
        'q_uz': '🌿 Qaysi o\'simlik havoni eng yaxshi tozalaydi?',
        'q_ru': '🌿 Какое растение лучше очищает воздух?',
        'q_en': '🌿 Which plant best purifies air?',
        'options': ['A) Kaktus', 'B) Xlorofitum ✅', 'C) Gulxayri'],
        'options_ru': ['A) Кактус', 'B) Хлорофитум ✅', 'C) Роза'],
        'options_en': ['A) Cactus', 'B) Chlorophytum ✅', 'C) Rose'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Xlorofitum havoni zararli moddalardan tozalaydi!',
        'info_ru': 'Правильно! Хлорофитум очищает воздух!',
        'info_en': 'Correct! Chlorophytum purifies air!',
        'points': 20
    },
    {
        'q_uz': '🌍 CO₂ ning atmosferada ortishi nima deb ataladi?',
        'q_ru': '🌍 Как называется увеличение CO₂?',
        'q_en': '🌍 What is CO₂ increase called?',
        'options': ['A) Global isish ✅', 'B) Kislorod yetishmasligi', 'C) Havo ifloslanishi'],
        'options_ru': ['A) Глобальное потепление ✅', 'B) Нехватка кислорода', 'C) Загрязнение'],
        'options_en': ['A) Global warming ✅', 'B) Oxygen shortage', 'C) Pollution'],
        'correct': 'A',
        'info_uz': 'To\'g\'ri! CO₂ ortishi global isishga olib keladi!',
        'info_ru': 'Правильно! Увеличение CO₂ ведет к потеплению!',
        'info_en': 'Correct! CO₂ increase causes warming!',
        'points': 10
    },
    {
        'q_uz': '♻️ Qog\'ozni qayta ishlash qancha energiya tejaydi?',
        'q_ru': '♻️ Сколько энергии экономит переработка бумаги?',
        'q_en': '♻️ How much energy does paper recycling save?',
        'options': ['A) 30%', 'B) 50%', 'C) 70% ✅'],
        'options_ru': ['A) 30%', 'B) 50%', 'C) 70% ✅'],
        'options_en': ['A) 30%', 'B) 50%', 'C) 70% ✅'],
        'correct': 'C',
        'info_uz': 'To\'g\'ri! Qog\'ozni qayta ishlash 70% energiya tejaydi!',
        'info_ru': 'Правильно! Переработка бумаги экономит 70%!',
        'info_en': 'Correct! Paper recycling saves 70%!',
        'points': 15
    },
    {
        'q_uz': '🐝 Asalari yo\'qolsa nima bo\'ladi?',
        'q_ru': '🐝 Что будет если исчезнут пчелы?',
        'q_en': '🐝 What if bees disappear?',
        'options': ['A) Hech nima', 'B) Oziq-ovqat tanqisligi ✅', 'C) Faqat asal kamayadi'],
        'options_ru': ['A) Ничего', 'B) Нехватка еды ✅', 'C) Только меньше меда'],
        'options_en': ['A) Nothing', 'B) Food shortage ✅', 'C) Only less honey'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Asalarilar changlatish uchun juda muhim!',
        'info_ru': 'Правильно! Пчелы важны для опыления!',
        'info_en': 'Correct! Bees are crucial for pollination!',
        'points': 20
    },
    {
        'q_uz': '🌊 Okeanlardagi plastik miqdori qancha?',
        'q_ru': '🌊 Сколько пластика в океанах?',
        'q_en': '🌊 How much plastic in oceans?',
        'options': ['A) 1 million tonna', 'B) 8 million tonna ✅', 'C) 50 million tonna'],
        'options_ru': ['A) 1 миллион тонн', 'B) 8 миллионов тонн ✅', 'C) 50 миллионов'],
        'options_en': ['A) 1 million tons', 'B) 8 million tons ✅', 'C) 50 million'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Har yili 8 million tonna plastik okeanlarga!',
        'info_ru': 'Правильно! 8 миллионов тонн ежегодно!',
        'info_en': 'Correct! 8 million tons yearly!',
        'points': 15
    },
    {
        'q_uz': '🌳 O\'rmonlar Yerning necha foizini egallaydi?',
        'q_ru': '🌳 Какой процент Земли занимают леса?',
        'q_en': '🌳 What percentage covered by forests?',
        'options': ['A) 10%', 'B) 31% ✅', 'C) 50%'],
        'options_ru': ['A) 10%', 'B) 31% ✅', 'C) 50%'],
        'options_en': ['A) 10%', 'B) 31% ✅', 'C) 50%'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! O\'rmonlar Yerning 31% ni egallaydi!',
        'info_ru': 'Правильно! Леса покрывают 31% Земли!',
        'info_en': 'Correct! Forests cover 31% of Earth!',
        'points': 10
    },
    {
        'q_uz': '🔋 Elektr energiyasining qaysi manbai eng toza?',
        'q_ru': '🔋 Какой источник электроэнергии самый чистый?',
        'q_en': '🔋 Which electricity source is cleanest?',
        'options': ['A) Ko\'mir', 'B) Shamol ✅', 'C) Gaz'],
        'options_ru': ['A) Уголь', 'B) Ветер ✅', 'C) Газ'],
        'options_en': ['A) Coal', 'B) Wind ✅', 'C) Gas'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Shamol energiyasi - eng toza!',
        'info_ru': 'Правильно! Ветер - самый чистый!',
        'info_en': 'Correct! Wind is cleanest!',
        'points': 10
    },
    {
        'q_uz': '🍎 Oziq-ovqat isrofi qancha?',
        'q_ru': '🍎 Сколько еды выбрасывается?',
        'q_en': '🍎 How much food is wasted?',
        'options': ['A) 10%', 'B) 33% ✅', 'C) 50%'],
        'options_ru': ['A) 10%', 'B) 33% ✅', 'C) 50%'],
        'options_en': ['A) 10%', 'B) 33% ✅', 'C) 50%'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Dunyoda 1/3 oziq-ovqat isrof qilinadi!',
        'info_ru': 'Правильно! 1/3 всей еды выбрасывается!',
        'info_en': 'Correct! 1/3 of all food is wasted!',
        'points': 15
    },
    {
        'q_uz': '🚗 Transport qancha CO₂ chiqaradi?',
        'q_ru': '🚗 Сколько CO₂ выделяет транспорт?',
        'q_en': '🚗 How much CO₂ does transport emit?',
        'options': ['A) 10%', 'B) 24% ✅', 'C) 50%'],
        'options_ru': ['A) 10%', 'B) 24% ✅', 'C) 50%'],
        'options_en': ['A) 10%', 'B) 24% ✅', 'C) 50%'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Transport 24% global CO₂ chiqaradi!',
        'info_ru': 'Правильно! Транспорт 24% выбросов!',
        'info_en': 'Correct! Transport 24% of emissions!',
        'points': 15
    },
    {
        'q_uz': '🌞 Quyosh bir soatda qancha energiya beradi?',
        'q_ru': '🌞 Сколько энергии дает Солнце за час?',
        'q_en': '🌞 How much energy from Sun in one hour?',
        'options': ['A) Bir kunlik', 'B) Bir yillik ✅', 'C) Bir oylik'],
        'options_ru': ['A) На день', 'B) На год ✅', 'C) На месяц'],
        'options_en': ['A) One day', 'B) One year ✅', 'C) One month'],
        'correct': 'B',
        'info_uz': 'Ajoyib! Quyosh bir soatda bir yillik energiya beradi!',
        'info_ru': 'Отлично! Солнце за час дает на год!',
        'info_en': 'Excellent! Sun gives one year in one hour!',
        'points': 20
    },
    {
        'q_uz': '🐢 Dengiz toshbaqalariga nima xavf soladi?',
        'q_ru': '🐢 Что угрожает морским черепахам?',
        'q_en': '🐢 What threatens sea turtles?',
        'options': ['A) Baliq ovlash', 'B) Plastik chiqindilar ✅', 'C) Iqlim'],
        'options_ru': ['A) Рыбалка', 'B) Пластиковые отходы ✅', 'C) Климат'],
        'options_en': ['A) Fishing', 'B) Plastic waste ✅', 'C) Climate'],
        'correct': 'B',
        'info_uz': 'To\'g\'ri! Plastik toshbaqalar uchun katta xavf!',
        'info_ru': 'Правильно! Пластик угроза для черепах!',
        'info_en': 'Correct! Plastic threatens turtles!',
        'points': 15
    }
]

# Kunlik faktlar
DAILY_FACTS = {
    'uz': [
        '🌍 Har yili 8 million tonna plastik okeanlarga tashlanadi.',
        '♻️ Qayta ishlangan 1 ta alyuminiy 3 soatlik TV energiya beradi!',
        '🌳 Dunyo bo\'ylab har yili 15 milliard daraxt kesiladi.',
        '💧 Dunyo aholisining 40% suv tanqisligidan aziyat chekadi.',
        '🚗 Transport 24% global CO₂ chiqindilarini tashkil qiladi.',
        '🌞 Quyosh bir soatda butun dunyo uchun bir yillik energiya!',
        '🍎 O\'rtacha amerikalik kuniga 4 kg chiqindi chiqaradi.',
        '🐝 Asalari yo\'qolsa, insoniyat 4 yilda yo\'qoladi.',
        '🌊 Plastik butilkalar 450 yil davomida chiriydi.',
        '🌲 Amazon o\'rmonlari dunyo kislorodining 20% ini beradi.'
    ],
    'ru': [
        '🌍 8 миллионов тонн пластика попадает в океаны ежегодно.',
        '♻️ Переработка одного алюминия дает 3 часа ТВ энергии!',
        '🌳 15 миллиардов деревьев вырубаются каждый год.',
        '💧 40% населения страдает от нехватки воды.',
        '🚗 Транспорт составляет 24% выбросов CO₂.',
        '🌞 Солнце за час дает энергию на год для всей Земли!',
        '🍎 Средний американец производит 4 кг отходов в день.',
        '🐝 Если пчелы исчезнут, человечество исчезнет за 4 года.',
        '🌊 Пластиковые бутылки разлагаются 450 лет.',
        '🌲 Амазонка производит 20% кислорода мира.'
    ],
    'en': [
        '🌍 8 million tons of plastic enter oceans yearly.',
        '♻️ Recycling one aluminum gives 3 hours of TV energy!',
        '🌳 15 billion trees are cut down each year.',
        '💧 40% of population suffers from water scarcity.',
        '🚗 Transport accounts for 24% of CO₂ emissions.',
        '🌞 Sun provides one year of energy in one hour!',
        '🍎 Average American produces 4kg waste daily.',
        '🐝 If bees disappear, humans in 4 years.',
        '🌊 Plastic bottles take 450 years to decompose.',
        '🌲 Amazon produces 20% of world\'s oxygen.'
    ]
}

# Challenge'lar
CHALLENGES = [
    {'name_uz': '7 kun plastikdan voz kechish', 'name_ru': '7 дней без пластика', 'name_en': '7 days no plastic', 'days': 7, 'reward': 100},
    {'name_uz': '30 kun velosipedda yurish', 'name_ru': '30 дней на велосипеде', 'name_en': '30 days cycling', 'days': 30, 'reward': 200},
    {'name_uz': '5 daraxt ekish', 'name_ru': 'Посадить 5 деревьев', 'name_en': 'Plant 5 trees', 'days': 30, 'reward': 150},
    {'name_uz': '1 hafta suvni tejash', 'name_ru': 'Неделя экономии воды', 'name_en': '1 week water saving', 'days': 7, 'reward': 80},
    {'name_uz': '10 kg chiqindini qayta ishlash', 'name_ru': '10 кг переработки', 'name_en': 'Recycle 10kg', 'days': 14, 'reward': 120}
]

user_state = {}

# ==================== KLAVIATURALAR ====================
def get_main_keyboard(lang='uz'):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if lang == 'uz':
        buttons = [
            ['🌱 Ekologik Savol', '📝 Testlar'],
            ['🎮 O\'yinlar', '📊 Reyting'],
            ['📰 Kunlik Fakt', '🎯 Challenge\'lar'],
            ['🌍 Saytimiz', '📞 Aloqa']
        ]
    elif lang == 'ru':
        buttons = [
            ['🌱 Эко Вопросы', '📝 Тесты'],
            ['🎮 Игры', '📊 Рейтинг'],
            ['📰 Факт Дня', '🎯 Испытания'],
            ['🌍 Сайт', '📞 Контакты']
        ]
    else:
        buttons = [
            ['🌱 Eco Questions', '📝 Tests'],
            ['🎮 Games', '📊 Rating'],
            ['📰 Daily Fact', '🎯 Challenges'],
            ['🌍 Website', '📞 Contact']
        ]
    
    for row in buttons:
        markup.row(*[types.KeyboardButton(btn) for btn in row])
    return markup

def get_quiz_keyboard(question, lang='uz'):
    markup = types.InlineKeyboardMarkup()
    
    if lang == 'uz':
        options = question['options']
    elif lang == 'ru':
        options = question['options_ru']
    else:
        options = question['options_en']
    
    for i, option in enumerate(options):
        callback = f"quiz_{i}_{question['correct']}_{question['points']}"
        markup.add(types.InlineKeyboardButton(option, callback_data=callback))
    return markup

def get_game_keyboard(lang='uz'):
    markup = types.InlineKeyboardMarkup()
    
    games = {
        'uz': [('♻️ Chiqindilarni saralash', 'game_sort'), 
               ('🌱 Daraxt ekish', 'game_tree'),
               ('💧 Suvni tejash', 'game_water')],
        'ru': [('♻️ Сортировка', 'game_sort'),
               ('🌱 Посадка деревьев', 'game_tree'),
               ('💧 Экономия воды', 'game_water')],
        'en': [('♻️ Waste Sorting', 'game_sort'),
               ('🌱 Tree Planting', 'game_tree'),
               ('💧 Water Saving', 'game_water')]
    }
    
    for text, callback in games.get(lang, games['uz']):
        markup.add(types.InlineKeyboardButton(text, callback_data=callback))
    
    markup.add(types.InlineKeyboardButton('🔙', callback_data='back_main'))
    return markup

def get_language_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton('🇺🇿 O\'zbekcha', callback_data='lang_uz'),
        types.InlineKeyboardButton('🇷🇺 Русский', callback_data='lang_ru')
    )
    markup.add(types.InlineKeyboardButton('🇬🇧 English', callback_data='lang_en'))
    return markup

def get_text(user_id, key):
    lang = db.get_language(user_id)
    return TRANSLATIONS.get(lang, TRANSLATIONS['uz']).get(key, '')

# ==================== BOT HANDLERLARI ====================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        chat_id = message.chat.id
        user = message.from_user
        
        db.add_user(user.id, user.username, user.first_name, user.last_name, 'uz')
        
        markup = get_language_keyboard()
        bot.send_message(
            chat_id,
            get_text(chat_id, 'select_language'),
            parse_mode='HTML',
            reply_markup=markup
        )
        logger.info(f"👤 /start from {user.first_name}")
    except Exception as e:
        logger.error(f"❌ /start error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def language_selection(call):
    try:
        chat_id = call.message.chat.id
        lang = call.data.split('_')[1]
        
        db.update_language(chat_id, lang)
        
        user = call.from_user
        name = user.first_name
        
        welcome_text = TRANSLATIONS[lang]['welcome'].format(name=name)
        
        bot.edit_message_text(
            welcome_text,
            chat_id=chat_id,
            message_id=call.message.message_id,
            parse_mode='HTML',
            reply_markup=get_main_keyboard(lang)
        )
        
        logger.info(f"🌍 {user.first_name} selected {lang}")
    except Exception as e:
        logger.error(f"❌ Language error: {e}")

@bot.message_handler(func=lambda message: message.text in ['🌱 Ekologik Savol', '🌱 Эко Вопросы', '🌱 Eco Questions'])
def eco_question_handler(message):
    try:
        chat_id = message.chat.id
        lang = db.get_language(chat_id)
        
        user_state[chat_id] = 'waiting_question'
        
        bot.send_message(
            chat_id,
            TRANSLATIONS[lang]['eco_question'],
            parse_mode='HTML',
            reply_markup=types.ReplyKeyboardRemove()
        )
        db.update_activity(chat_id)
    except Exception as e:
        logger.error(f"❌ Eco question error: {e}")

@bot.message_handler(func=lambda message: message.text in ['📝 Testlar', '📝 Тесты', '📝 Tests'])
def test_menu(message):
    try:
        chat_id = message.chat.id
        lang = db.get_language(chat_id)
        
        markup = types.InlineKeyboardMarkup()
        start_text = '▶️ Boshlash' if lang == 'uz' else '▶️ Начать' if lang == 'ru' else '▶️ Start'
        markup.add(types.InlineKeyboardButton(start_text, callback_data='start_quiz'))
        
        bot.send_message(
            chat_id,
            TRANSLATIONS[lang]['test_menu'],
            parse_mode='HTML',
            reply_markup=markup
        )
        db.update_activity(chat_id)
    except Exception as e:
        logger.error(f"❌ Test menu error: {e}")

@bot.callback_query_handler(func=lambda call: call.data == 'start_quiz')
def start_quiz(call):
    try:
        chat_id = call.message.chat.id
        lang = db.get_language(chat_id)
        
        random_q = random.choice(QUIZ_QUESTIONS)
        user_state[chat_id] = {'action': 'quiz', 'question': random_q}
        
        markup = get_quiz_keyboard(random_q, lang)
        
        if lang == 'uz':
            q_text = random_q['q_uz']
        elif lang == 'ru':
            q_text = random_q['q_ru']
        else:
            q_text = random_q['q_en']
        
        bot.send_message(
            chat_id,
            f"📝 <b>TEST</b>\n\n{q_text}\n\n<i>{random_q['points']} ball</i>",
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"❌ Start quiz error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('quiz_'))
def handle_quiz_callback(call):
    try:
        chat_id = call.message.chat.id
        lang = db.get_language(chat_id)
        
        data = call.data.split('_')
        selected_index = data[1]
        correct_answer = data[2]
        points = int(data[3])
        
        question_data = user_state[chat_id]['question']
        
        if lang == 'uz':
            q_text = question_data['q_uz']
            info = question_data['info_uz']
            options = question_data['options']
        elif lang == 'ru':
            q_text = question_data['q_ru']
            info = question_data['info_ru']
            options = question_data['options_ru']
        else:
            q_text = question_data['q_en']
            info = question_data['info_en']
            options = question_data['options_en']
        
        is_correct = selected_index == correct_answer
        
        if is_correct:
            db.add_score(chat_id, points)
            bot.answer_callback_query(call.id, text=f"✅ To'g'ri! +{points}")
            
            stats = db.get_user_stats(chat_id)
            total = stats[0] if stats else points
            
            text = TRANSLATIONS[lang]['correct_answer'].format(
                info=info, points=points, total_score=total
            )
        else:
            bot.answer_callback_query(call.id, text="❌ Noto'g'ri", show_alert=True)
            text = TRANSLATIONS[lang]['wrong_answer'].format(
                correct=options[int(correct_answer)], info=info
            )
        
        db.record_quiz(chat_id, q_text, options[int(selected_index)], 
                      options[int(correct_answer)], is_correct, points if is_correct else 0)
        
        bot.send_message(chat_id, text, parse_mode='HTML')
        
        time.sleep(1)
        markup = types.InlineKeyboardMarkup()
        continue_text = '🔄 Yangi test' if lang == 'uz' else '🔄 Новый тест' if lang == 'ru' else '🔄 New Test'
        markup.add(types.InlineKeyboardButton(continue_text, callback_data='new_quiz'))
        
        stats_text = '📊 Statistika' if lang == 'uz' else '📊 Статистика' if lang == 'ru' else '📊 Stats'
        markup.add(types.InlineKeyboardButton(stats_text, callback_data='my_stats'))
        
        back_text = '🏠 Bosh menyu' if lang == 'uz' else '🏠 Меню' if lang == 'ru' else '🏠 Menu'
        markup.add(types.InlineKeyboardButton(back_text, callback_data='back_main'))
        
        bot.send_message(chat_id, TRANSLATIONS[lang]['continue'], reply_markup=markup)
        
    except Exception as e:
        logger.error(f"❌ Quiz callback error: {e}")

@bot.callback_query_handler(func=lambda call: call.data == 'new_quiz')
def new_quiz_handler(call):
    start_quiz(call)

@bot.message_handler(func=lambda message: message.text in ['🎮 O\'yinlar', '🎮 Игры', '🎮 Games'])
def game_menu(message):
    try:
        chat_id = message.chat.id
        lang = db.get_language(chat_id)
        
        bot.send_message(
            chat_id,
            TRANSLATIONS[lang]['game_menu'],
            parse_mode='HTML',
            reply_markup=get_game_keyboard(lang)
        )
        db.update_activity(chat_id)
    except Exception as e:
        logger.error(f"❌ Game menu error: {e}")

# O'YIN 1: Chiqindilarni saralash
@bot.callback_query_handler(func=lambda call: call.data == 'game_sort')
def waste_sorting_game(call):
    try:
        chat_id = call.message.chat.id
        lang = db.get_language(chat_id)
        
        user_state[chat_id] = {
            'action': 'game_sort',
            'level': 1,
            'score': 0,
            'total_items': 10
        }
        
        next_sorting_item(chat_id, lang)
    except Exception as e:
        logger.error(f"❌ Waste sorting error: {e}")

def next_sorting_item(chat_id, lang):
    try:
        game_state = user_state[chat_id]
        
        if game_state['level'] > game_state['total_items']:
            final_score = game_state['score']
            db.add_score(chat_id, final_score)
            db.add_eco_points(chat_id, final_score // 2)
            
            if final_score >= 70:
                text = TRANSLATIONS[lang]['game_won'].format(
                    points=final_score, eco_points=final_score // 2
                )
            else:
                text = TRANSLATIONS[lang]['game_lost']
            
            bot.send_message(chat_id, text, parse_mode='HTML')
            return
        
        items = [
            {'uz': 'Plastik shisha', 'ru': 'Пластиковая бутылка', 'en': 'Plastic bottle', 'type': 'plastic'},
            {'uz': 'Qog\'oz', 'ru': 'Бумага', 'en': 'Paper', 'type': 'paper'},
            {'uz': 'Shisha', 'ru': 'Стекло', 'en': 'Glass', 'type': 'glass'},
            {'uz': 'Alyuminiy quti', 'ru': 'Алюминиевая банка', 'en': 'Aluminum can', 'type': 'metal'},
            {'uz': 'Organik', 'ru': 'Органика', 'en': 'Organic', 'type': 'organic'}
        ]
        
        item = random.choice(items)
        game_state['current_item'] = item
        
        if lang == 'uz':
            item_name = item['uz']
            q_text = f"♻️ <b>{game_state['level']}/{game_state['total_items']}</b>\n\nQaysi idish?\n\n<b>{item_name}</b>"
            buttons = [('🔵 Plastik', 'sort_plastic'), ('🟢 Qog\'oz', 'sort_paper'), 
                      ('🟤 Shisha', 'sort_glass'), ('🟡 Metall', 'sort_metal'), ('🟤 Organik', 'sort_organic')]
        elif lang == 'ru':
            item_name = item['ru']
            q_text = f"♻️ <b>{game_state['level']}/{game_state['total_items']}</b>\n\nКуда?\n\n<b>{item_name}</b>"
            buttons = [('🔵 Пластик', 'sort_plastic'), ('🟢 Бумага', 'sort_paper'),
                      ('🟤 Стекло', 'sort_glass'), ('🟡 Металл', 'sort_metal'), ('🟤 Органика', 'sort_organic')]
        else:
            item_name = item['en']
            q_text = f"♻️ <b>{game_state['level']}/{game_state['total_items']}</b>\n\nWhere?\n\n<b>{item_name}</b>"
            buttons = [('🔵 Plastic', 'sort_plastic'), ('🟢 Paper', 'sort_paper'),
                      ('🟤 Glass', 'sort_glass'), ('🟡 Metal', 'sort_metal'), ('🟤 Organic', 'sort_organic')]
        
        markup = types.InlineKeyboardMarkup()
        for text, callback in buttons:
            markup.add(types.InlineKeyboardButton(text, callback_data=callback))
        
        bot.send_message(chat_id, q_text, parse_mode='HTML', reply_markup=markup)
    except Exception as e:
        logger.error(f"❌ Next sorting error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('sort_'))
def handle_sorting(call):
    try:
        chat_id = call.message.chat.id
        lang = db.get_language(chat_id)
        
        selected_type = call.data.split('_')[1]
        game_state = user_state[chat_id]
        current_item = game_state['current_item']
        
        if selected_type == current_item['type']:
            game_state['score'] += 10
            bot.answer_callback_query(call.id, text="✅ +10")
        else:
            bot.answer_callback_query(call.id, text="❌")
        
        game_state['level'] += 1
        bot.delete_message(chat_id, call.message.message_id)
        next_sorting_item(chat_id, lang)
    except Exception as e:
        logger.error(f"❌ Handle sorting error: {e}")

# O'YIN 2: Daraxt ekish
@bot.callback_query_handler(func=lambda call: call.data == 'game_tree')
def tree_planting_game(call):
    try:
        chat_id = call.message.chat.id
        lang = db.get_language(chat_id)
        
        user_state[chat_id] = {
            'action': 'game_tree',
            'planted': 0,
            'target': 10
        }
        
        if lang == 'uz':
            text = "🌱 <b>DARAXT EKISH</b>\n\n10 ta daraxt eking!\n\nTezroq!"
            btn_text = "🌳 Ekish"
        elif lang == 'ru':
            text = "🌱 <b>ПОСАДКА</b>\n\nПосадите 10 деревьев!\n\nБыстрее!"
            btn_text = "🌳 Посадить"
        else:
            text = "🌱 <b>PLANT TREES</b>\n\nPlant 10 trees!\n\nQuick!"
            btn_text = "🌳 Plant"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(btn_text, callback_data='plant_tree'))
        
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)
    except Exception as e:
        logger.error(f"❌ Tree planting error: {e}")

@bot.callback_query_handler(func=lambda call: call.data == 'plant_tree')
def plant_tree(call):
    try:
        chat_id = call.message.chat.id
        lang = db.get_language(chat_id)
        
        game_state = user_state[chat_id]
        game_state['planted'] += 1
        
        if game_state['planted'] >= game_state['target']:
            points = 100
            eco_points = 50
            db.add_score(chat_id, points)
            db.add_eco_points(chat_id, eco_points)
            
            text = TRANSLATIONS[lang]['game_won'].format(points=points, eco_points=eco_points)
            bot.send_message(chat_id, text, parse_mode='HTML')
        else:
            remaining = game_state['target'] - game_state['planted']
            
            if lang == 'uz':
                text = f"🌳 {game_state['planted']}/10\n\nYana {remaining} ta!"
            elif lang == 'ru':
                text = f"🌳 {game_state['planted']}/10\n\nОсталось {remaining}!"
            else:
                text = f"🌳 {game_state['planted']}/10\n\n{remaining} more!"
            
            bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, parse_mode='HTML')
    except Exception as e:
        logger.error(f"❌ Plant tree error: {e}")

# O'YIN 3: Suvni tejash
@bot.callback_query_handler(func=lambda call: call.data == 'game_water')
def water_saving_game(call):
    try:
        chat_id = call.message.chat.id
        lang = db.get_language(chat_id)
        
        user_state[chat_id] = {
            'action': 'game_water',
            'saved': 0,
            'wasted': 0,
            'rounds': 0
        }
        
        next_water_scenario(chat_id, lang)
    except Exception as e:
        logger.error(f"❌ Water game error: {e}")

def next_water_scenario(chat_id, lang):
    try:
        game_state = user_state[chat_id]
        
        if game_state['rounds'] >= 5:
            points = game_state['saved'] * 20
            eco_points = game_state['saved'] * 10
            db.add_score(chat_id, points)
            db.add_eco_points(chat_id, eco_points)
            
            if lang == 'uz':
                text = f"💧 <b>Tugadi!</b>\n\nTejadingiz: {game_state['saved']}\nIsrof: {game_state['wasted']}\n\n+{points} ball\n🌱 +{eco_points} eco"
            elif lang == 'ru':
                text = f"💧 <b>Конец!</b>\n\nСэкономили: {game_state['saved']}\nПотеряли: {game_state['wasted']}\n\n+{points} баллов\n🌱 +{eco_points} eco"
            else:
                text = f"💧 <b>Game Over!</b>\n\nSaved: {game_state['saved']}\nWasted: {game_state['wasted']}\n\n+{points} points\n🌱 +{eco_points} eco"
            
            bot.send_message(chat_id, text, parse_mode='HTML')
            return
        
        scenarios = {
            'uz': [
                "🚰 Kran ochiq qoldi. Nima qilasiz?",
                "🚿 Dushda 15 daqiqa. Nima qilasiz?",
                "💧 Idish yuvayapsiz. Suv oqib turibdi."
            ],
            'ru': [
                "🚰 Кран открыт. Что сделаете?",
                "🚿 Душ 15 минут. Что сделаете?",
                "💧 Моете посуду. Вода течет."
            ],
            'en': [
                "🚰 Tap left open. What do you do?",
                "🚿 Shower 15 min. What do you do?",
                "💧 Washing dishes. Water running."
            ]
        }
        
        scenario = random.choice(scenarios[lang])
        game_state['rounds'] += 1
        
        if lang == 'uz':
            text = f"💧 <b>{game_state['rounds']}/5</b>\n\n{scenario}"
            save_btn = "✅ Tejayman"
            waste_btn = "❌ E'tibor bermayman"
        elif lang == 'ru':
            text = f"💧 <b>{game_state['rounds']}/5</b>\n\n{scenario}"
            save_btn = "✅ Экономлю"
            waste_btn = "❌ Игнорирую"
        else:
            text = f"💧 <b>{game_state['rounds']}/5</b>\n\n{scenario}"
            save_btn = "✅ Save"
            waste_btn = "❌ Ignore"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(save_btn, callback_data='water_save'))
        markup.add(types.InlineKeyboardButton(waste_btn, callback_data='water_waste'))
        
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)
    except Exception as e:
        logger.error(f"❌ Next water error: {e}")

@bot.callback_query_handler(func=lambda call: call.data in ['water_save', 'water_waste'])
def handle_water_choice(call):
    try:
        chat_id = call.message.chat.id
        lang = db.get_language(chat_id)
        
        game_state = user_state[chat_id]
        
        if call.data == 'water_save':
            game_state['saved'] += 1
            bot.answer_callback_query(call.id, text="✅")
        else:
            game_state['wasted'] += 1
            bot.answer_callback_query(call.id, text="❌")
        
        bot.delete_message(chat_id, call.message.message_id)
        next_water_scenario(chat_id, lang)
    except Exception as e:
        logger.error(f"❌ Water choice error: {e}")

@bot.message_handler(func=lambda message: message.text in ['📊 Reyting', '📊 Рейтинг', '📊 Rating'])
def show_leaderboard(message):
    try:
        chat_id = message.chat.id
        lang = db.get_language(chat_id)
        
        leaderboard = db.get_leaderboard(10)
        
        if not leaderboard:
            bot.send_message(chat_id, "📊 Reyting bo'sh")
            return
        
        text = TRANSLATIONS[lang]['leaderboard']
        
        for i, (first_name, username, score, correct, eco) in enumerate(leaderboard, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            user_tag = f"@{username}" if username else first_name
            text += f"{medal} <b>{user_tag}</b> - {score} ball (🌱 {eco})\n"
        
        bot.send_message(chat_id, text, parse_mode='HTML')
        db.update_activity(chat_id)
    except Exception as e:
        logger.error(f"❌ Leaderboard error: {e}")

@bot.message_handler(func=lambda message: message.text in ['📰 Kunlik Fakt', '📰 Факт Дня', '📰 Daily Fact'])
def daily_fact(message):
    try:
        chat_id = message.chat.id
        lang = db.get_language(chat_id)
        
        fact = random.choice(DAILY_FACTS[lang])
        
        bot.send_message(
            chat_id,
            TRANSLATIONS[lang]['daily_fact'].format(fact=fact),
            parse_mode='HTML'
        )
        db.update_activity(chat_id)
    except Exception as e:
        logger.error(f"❌ Daily fact error: {e}")

@bot.message_handler(func=lambda message: message.text in ['🎯 Challenge\'lar', '🎯 Испытания', '🎯 Challenges'])
def show_challenges(message):
    try:
        chat_id = message.chat.id
        lang = db.get_language(chat_id)
        
        text = TRANSLATIONS[lang]['challenges'] + "\n"
        
        for challenge in CHALLENGES:
            if lang == 'uz':
                name = challenge['name_uz']
            elif lang == 'ru':
                name = challenge['name_ru']
            else:
                name = challenge['name_en']
            
            text += f"• {name} - {challenge['reward']} ball\n"
        
        bot.send_message(chat_id, text, parse_mode='HTML')
        db.update_activity(chat_id)
    except Exception as e:
        logger.error(f"❌ Challenges error: {e}")

@bot.message_handler(func=lambda message: message.text in ['🌍 Saytimiz', '🌍 Сайт', '🌍 Website'])
def send_website(message):
    try:
        chat_id = message.chat.id
        lang = db.get_language(chat_id)
        
        markup = types.InlineKeyboardMarkup()
        visit_text = '🌐 Saytga o\'tish' if lang == 'uz' else '🌐 Перейти' if lang == 'ru' else '🌐 Visit'
        markup.add(types.InlineKeyboardButton(visit_text, url=WEBSITE_URL))
        
        bot.send_message(
            chat_id,
            TRANSLATIONS[lang]['website'],
            parse_mode='HTML',
            reply_markup=markup
        )
        db.update_activity(chat_id)
    except Exception as e:
        logger.error(f"❌ Website error: {e}")

@bot.message_handler(func=lambda message: message.text in ['📞 Aloqa', '📞 Контакты', '📞 Contact'])
def contact_handler(message):
    try:
        chat_id = message.chat.id
        lang = db.get_language(chat_id)
        
        bot.send_message(
            chat_id,
            TRANSLATIONS[lang]['contact'],
            parse_mode='HTML',
            reply_markup=get_main_keyboard(lang)
        )
        db.update_activity(chat_id)
    except Exception as e:
        logger.error(f"❌ Contact error: {e}")

@bot.callback_query_handler(func=lambda call: call.data == 'my_stats')
def show_user_stats(call):
    try:
        chat_id = call.message.chat.id
        lang = db.get_language(chat_id)
        
        stats = db.get_user_stats(chat_id)
        
        if stats:
            total_score, quizzes, correct, games_played, games_won, eco_points = stats
            accuracy = (correct / quizzes * 100) if quizzes > 0 else 0
            
            text = TRANSLATIONS[lang]['stats'].format(
                score=total_score,
                eco_points=eco_points,
                quizzes=quizzes,
                correct=correct,
                games_played=games_played,
                games_won=games_won,
                accuracy=round(accuracy, 1)
            )
            
            bot.send_message(chat_id, text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"❌ Stats error: {e}")

@bot.callback_query_handler(func=lambda call: call.data == 'back_main')
def back_to_main(call):
    try:
        chat_id = call.message.chat.id
        lang = db.get_language(chat_id)
        
        bot.delete_message(chat_id, call.message.message_id)
        bot.send_message(chat_id, "🏠", reply_markup=get_main_keyboard(lang))
    except Exception as e:
        logger.error(f"❌ Back to main error: {e}")

@bot.message_handler(commands=['help', 'помощь'])
def help_command(message):
    try:
        chat_id = message.chat.id
        lang = db.get_language(chat_id)
        
        bot.send_message(chat_id, TRANSLATIONS[lang]['help'], parse_mode='HTML')
        db.update_activity(chat_id)
    except Exception as e:
        logger.error(f"❌ Help error: {e}")

@bot.message_handler(commands=['commands', 'команды'])
def commands_list(message):
    try:
        chat_id = message.chat.id
        lang = db.get_language(chat_id)
        
        bot.send_message(chat_id, TRANSLATIONS[lang]['commands'], parse_mode='HTML')
        db.update_activity(chat_id)
    except Exception as e:
        logger.error(f"❌ Commands error: {e}")

@bot.message_handler(commands=['stats'])
def user_stats_command(message):
    try:
        chat_id = message.chat.id
        lang = db.get_language(chat_id)
        
        stats = db.get_user_stats(chat_id)
        
        if stats:
            total_score, quizzes, correct, games_played, games_won, eco_points = stats
            accuracy = (correct / quizzes * 100) if quizzes > 0 else 0
            
            text = TRANSLATIONS[lang]['stats'].format(
                score=total_score,
                eco_points=eco_points,
                quizzes=quizzes,
                correct=correct,
                games_played=games_played,
                games_won=games_won,
                accuracy=round(accuracy, 1)
            )
            
            bot.send_message(chat_id, text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"❌ Stats command error: {e}")

@bot.message_handler(commands=['test'])
def test_command(message):
    test_menu(message)

@bot.message_handler(commands=['game'])
def game_command(message):
    game_menu(message)

@bot.message_handler(commands=['fact'])
def fact_command(message):
    daily_fact(message)

@bot.message_handler(commands=['lang', 'тил', 'language'])
def change_language(message):
    try:
        chat_id = message.chat.id
        
        markup = get_language_keyboard()
        bot.send_message(
            chat_id,
            get_text(chat_id, 'select_language'),
            parse_mode='HTML',
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"❌ Change language error: {e}")

# Savollarga javob
@bot.message_handler(func=lambda message: message.chat.id in user_state and user_state[message.chat.id] == 'waiting_question')
def answer_eco_question(message):
    try:
        chat_id = message.chat.id
        lang = db.get_language(chat_id)
        text = message.text.lower()
        
        eco_answers = {
            'uz': {
                'global isish': '🌍 Global isish - Yer haroratining ko\'tarilishi. CO₂ chiqindilari sabab.',
                'plastik': '🚫 Plastik 100-450 yil chiriydi. Qayta ishlash kerak!',
                'suv': '💧 Suvni tejang! Kranni yoping, dushda 5 daqiqadan ortiq yuvinmang.',
                'daraxt': '🌳 Daraxtlar kislorod ishlab chiqaradi va havoni tozalaydi.',
                'energiya': '⚡ LED lampalar 80-90% energiya tejaydi.',
                'qayta ishlash': '♻️ Qayta ishlash - chiqindilarni qayta ishlatish. Tabiatni asraydi!'
            },
            'ru': {
                'глобальное потепление': '🌍 Глобальное потепление - повышение температуры Земли.',
                'пластик': '🚫 Пластик разлагается 100-450 лет. Нужно перерабатывать!',
                'вода': '💧 Экономьте воду! Закрывайте кран, душ не более 5 минут.',
                'дерево': '🌳 Деревья производят кислород и очищают воздух.',
                'энергия': '⚡ LED лампы экономят 80-90% энергии.',
                'переработка': '♻️ Переработка - повторное использование отходов.'
            },
            'en': {
                'global warming': '🌍 Global warming - Earth temperature rise due to CO₂.',
                'plastic': '🚫 Plastic takes 100-450 years to decompose. Recycle!',
                'water': '💧 Save water! Close taps, shower max 5 minutes.',
                'tree': '🌳 Trees produce oxygen and clean air.',
                'energy': '⚡ LED bulbs save 80-90% energy.',
                'recycling': '♻️ Recycling - reusing waste. Protects nature!'
            }
        }
        
        found = False
        for key in eco_answers[lang]:
            if key in text:
                bot.send_message(chat_id, eco_answers[lang][key])
                found = True
                break
        
        if not found:
            if lang == 'uz':
                bot.send_message(chat_id, "🤔 Tushunmadim. Boshqa savol bering.")
            elif lang == 'ru':
                bot.send_message(chat_id, "🤔 Не понял. Задайте другой вопрос.")
            else:
                bot.send_message(chat_id, "🤔 Don't understand. Ask another question.")
        
        user_state[chat_id] = None
        db.update_activity(chat_id)
        
        time.sleep(1)
        bot.send_message(chat_id, "Boshqa savol?", reply_markup=get_main_keyboard(lang))
    except Exception as e:
        logger.error(f"❌ Answer question error: {e}")

# Barcha xabarlarni qayta ishlash
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        chat_id = message.chat.id
        lang = db.get_language(chat_id)
        
        # Agar foydalanuvchi holatda bo'lmasa
        if chat_id not in user_state or user_state[chat_id] is None:
            if lang == 'uz':
                bot.send_message(
                    chat_id,
                    "🤔 Men sizni tushunmadim. Iltimos, menyudan tanlang:",
                    reply_markup=get_main_keyboard(lang)
                )
            elif lang == 'ru':
                bot.send_message(
                    chat_id,
                    "🤔 Я не понял. Пожалуйста, выберите из меню:",
                    reply_markup=get_main_keyboard(lang)
                )
            else:
                bot.send_message(
                    chat_id,
                    "🤔 I don't understand. Please choose from menu:",
                    reply_markup=get_main_keyboard(lang)
                )
        
        db.update_activity(chat_id)
        logger.info(f"💬 Message from {message.from_user.first_name}: {message.text}")
    except Exception as e:
        logger.error(f"❌ Handle all messages error: {e}")

# ==================== BOTNI ISHGA TUSHIRISH ====================
if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("🌱 YOSH EKOLOGLAR BOT ISHGA TUSHDI")
    logger.info("=" * 50)
    logger.info(f"📊 25 ta test yuklandi")
    logger.info(f"🎮 3 ta o'yin tayyor")
    logger.info(f"🌍 3 ta til: O'zbekcha, Русский, English")
    logger.info(f"🌐 Sayt: {WEBSITE_URL}")
    logger.info("=" * 50)
    
    print("\n" + "=" * 50)
    print(" YOSH EKOLOGLAR BOT")
    print("=" * 50)
    print("✅ Bot ishga tushdi!")
    print("📊 25 test savoli")
    print("🎮 3 interaktiv o'yin")
    print("🌍 3 til (UZ, RU, EN)")
    print(f"🌐 Sayt: {WEBSITE_URL}")
    print("=" * 50)
    print("\n🛑 To'xtatish uchun Ctrl+C bosing\n")
    
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=10)
    except KeyboardInterrupt:
        logger.info("👋 Bot to'xtatildi")
        print("\n👋 Bot to'xtatildi")
    except Exception as e:
        logger.error(f"❌ Xatolik: {e}")
        print(f"\n❌ Xatolik: {e}")
