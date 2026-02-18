const { Telegraf, Markup } = require('telegraf');

// Bot tokeningizni @BotFather'dan oling va bu yerga qo'ying
const bot = new Telegraf('8055090268:AAHtu9cy9lnZw_GFZqo8mc860Bj9G3H7vOU');

// Asosiy menyu tugmalari
const mainMenu = Markup.keyboard([
    ['❓ Savol-javob', '🎮 Qiziqarli Test'],
    ['🌐 Bizning saytimiz', '🌿 Ekologik maslahat']
]).resize();

// Start buyrug'i
bot.start((ctx) => {
    ctx.reply(`Salom ${ctx.from.first_name}! Yosh ekologlar botiga xush kelibsiz. 🌍\nTabiatni birgalikda asraymiz!`, mainMenu);
});

// Saytga havola tugmasi
bot.hears('🌐 Bizning saytimiz', (ctx) => {
    ctx.reply('Bizning rasmiy saytimizga tashrif buyuring:', 
        Markup.inlineKeyboard([
            [Markup.button.url('Saytga o‘tish', 'https://sizning-saytingiz.uz')]
        ])
    );
});

// Savol-javob bo'limi
bot.hears('❓ Savol-javob', (ctx) => {
    ctx.reply('Ekologiya haqida savolingiz bo\'lsa, yozib qoldiring. Biz tez orada javob beramiz! (Hozircha bot test rejimida)');
});

// Oddiy ekologik maslahatlar
bot.hears('🌿 Ekologik maslahat', (ctx) => {
    const tips = [
        "Plastik paketlardan voz keching, matoli sumkalardan foydalaning! 🛍️",
        "Tish yuvayotganda suvni o'chirib qo'ying! 💧",
        "Daraxt eking — bu kelajak uchun eng yaxshi investitsiya! 🌳",
        "Chiroqni xonadan chiqayotganda o'chirishni unutmang! 💡"
    ];
    const randomTip = tips[Math.floor(Math.random() * tips.length)];
    ctx.reply(randomTip);
});

// Qiziqarli Test (Viktorina)
bot.hears('🎮 Qiziqarli Test', (ctx) => {
    ctx.replyWithQuiz(
        'Plastik shishaning tabiatda parchalanishi uchun taxminan qancha vaqt ketadi?',
        ['50 yil', '100 yil', '450 yil', '20 yil'],
        { correct_option_id: 2 } // To'g'ri javob: 450 yil
    );
});

bot.launch();

// Xatoliklarni ushlash
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));

console.log('Bot muvaffaqiyatli ishga tushdi...');
