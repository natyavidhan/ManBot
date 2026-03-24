const { Client, GatewayIntentBits } = require("discord.js")
const client = new Client({
     intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
     ] 
    });

client.on('messageCreate', message => {
    if (message.author.bot) return;
    message.reply({
        content: "WE NEED TO ADD STUFF"
    });
    console.log(message)
});
client.login(
    "TOKEN MAN"
) 
