import os, sys, time
import logging
from telegram.ext import CommandHandler, MessageHandler, Filters, Updater
from telegram import KeyboardButton, ReplyKeyboardMarkup, ChatAction
import subprocess
import tempfile
from threading import Thread

messageIntervall=1

command_blacklist=[
    'nano ',
    'vi '
    ]

def first_lower(s):
    if len(s) == 0:
        return s
    else:
        return s[0].lower() + s[1:]
	  
class bufferMessage(Thread):
    def __init__(self):
        self.lastbot=None
        self.lastupdate=None
        self.running=True
        self.buffer=''
        Thread.__init__(self)

    def run(self):
        while self.running==True:
            if self.buffer!='':
                print(self.buffer)
                self.send_long_message(self.lastbot, self.lastupdate, self.buffer)
                self.buffer=''
            else:
                time.sleep(messageIntervall)
	
    def addMessage(self, bot, update, message):
        self.lastbot=bot
        self.lastupdate=update
        self.buffer=self.buffer+'\n'+message
		
    def send_long_message(self, bot, update, message_text='Empty message'):
        restlength=len(message_text)
        while restlength>0:
            bot.send_message(chat_id=update.message.chat_id, text=message_text)
            restlength=restlength-4096

class telegramShell():
    def __init__(self, configFile):
        self.help_text=''
        self.servername=''
        self.token=''
        self.commands=[]
        self.names=[]
        self.infos=[]
        self.myFunctions = {}
        error=self.readFile(configFile)
        if not error:
            self.updater = Updater(token=self.token)
            self.dispatcher = self.updater.dispatcher
            logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.INFO)
            self.sender = bufferMessage()
            self.sender.setName('buffer_sender')
            self.sender.start()
            if self.servername != '':
                self.help_text=self.servername+'\n'
            for i in range(len(self.names)):
                self.addCmd2(self.names[i],self.infos[i],self.commands[i])
                self.help_text=self.help_text+'/'+self.names[i]+' - '+self.infos[i]+'\n'
            self.help_text=self.help_text+'[shell] - Simply type shell commands\n/menu - Show menu\n/help - Command-List'
            echo_handler = MessageHandler(Filters.text,self.shellMessageHandler)
            self.dispatcher.add_handler(echo_handler)
            start_handler = CommandHandler('start',self.helpHandler)
            self.dispatcher.add_handler(start_handler)
            help_handler = CommandHandler('help',self.helpHandler)
            self.dispatcher.add_handler(help_handler)
            menu_handler = CommandHandler('menu',self.menuHandler)
            self.dispatcher.add_handler(menu_handler)
            self.updater.start_polling()
            print('Telegram-Server successfully started!')
            self.updater.idle()
            print('Telegram-Server stopped!')
            self.sender.running=False
            self.updater.stop()
        else:
            print('**Error**\nCheck config.ini\nLine '+str(error))

#################### OPEN FUNCTIONS ################################################
    def readFile(self,configFile): # Read configFile
        for line in configFile:
            if line.find('telegramToken:')==0:
                self.token=self.getLineContent(line)
            elif line.find('serverName:')==0:
                self.servername=self.getLineContent(line)
            elif line.find('name:')==0:
                self.names.append(self.getLineContent(line))
            elif line.find('command:')==0:
                self.commands.append(self.getLineContent(line))
            elif line.find('info:')==0:
                self.infos.append(self.getLineContent(line))

        if len(self.commands) != len(self.names) and len(self.commands) != len(self.infos):
            print('**ERROR**\nCommands found: '+str(len(self.commands))+'\nNames found: '+str(len(self.names))+'\nInfos found: '+str(len(self.infos)))
            return 0
        elif self.token=='':
            print('Please add "telegramToken: ***" entry in config.ini')
            return -1

    def getLineContent(self,line): # Returns values in '' out of a String
        start=line.find("'")+1
        end=line.find("'",start)
        print(line[start:end])
        return line[start:end]

    def addCmd(self, name, info, command):  # Create CommandHandler and add to dispatcher
        def cmd(bot, update):
                bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
                systeminfo=self.exec_command(command)
                if systeminfo:
                    if systeminfo!="":
                        self.send_long_message(bot, update, systeminfo)
                    else:
                        bot.send_message(chat_id=update.message.chat_id, text='Empty command')
                else:
                    bot.send_message(chat_id=update.message.chat_id, text='Error in command')
        handler = CommandHandler(name,cmd)
        self.dispatcher.add_handler(handler)

    def exec_command(self, cmd_str): # Execute Shell-Command
            systeminfo=''
            with tempfile.TemporaryFile() as tempf:
                    proc = subprocess.Popen(cmd_str,stdout=tempf, shell=True)
                    proc.wait()
                    tempf.seek(0)
                    systeminfo=systeminfo+tempf.read().decode('utf-8')
            print('CMD: '+cmd_str+'\nANSWER: \n'+systeminfo+'\n')
            return systeminfo
			
    def addCmd2(self, name, info, command):  # Create CommandHandler and add to dispatcher
        def cmd(bot, update):
                bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
                self.exec_command2(bot, update, command)
        handler = CommandHandler(name,cmd)
        self.dispatcher.add_handler(handler)

    def exec_command2(self, bot, update, cmd_str):
        print('CMD: '+cmd_str)
        cmd = subprocess.Popen(cmd_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        #for line in cmd.stdout.readline():
        for line in iter(cmd.stdout.readline, ''):
            line = line.decode('utf-8').replace('\r', '').replace('\n', '')
            print(line)
            #self.send_long_message(bot, update, line)
            self.sender.addMessage(bot, update, line)
            sys.stdout.flush()
            if line=='':
                path=subprocess.Popen('pwd -P', shell=True, stdout=subprocess.PIPE)
                path=path.stdout.readline().decode('utf-8')
                path = path.replace('\r', '').replace('\n', '')
                print('shell:'+path+'$')
                #self.send_long_message(bot, update, 'shell:'+path+'$')
                self.sender.addMessage(bot, update, 'shell:'+path+'$')
                break
	
    def send_long_message(self, bot, update, message_text='Empty message'):
        restlength=len(message_text)
        while restlength>0:
            bot.send_message(chat_id=update.message.chat_id, text=message_text)
            restlength=restlength-4096

#################### Action Handler #################################################

# SHELL HANDLER
    def shellMessageHandler(self,bot, update):
            cmd_string=update.message.text
            if cmd_string and cmd_string!="":
                if cmd_string.find('cd ')==0:
                    try:
                        os.chdir(cmd_string[3:])
                    except:
                        self.send_long_message(bot, update, 'No such directory')
                elif self.checkBlacklist(cmd_string)==True:
                    #self.send_long_message(bot, update, self.exec_command2(first_lower(cmd_string)))
                    self.exec_command2(bot, update, first_lower(cmd_string))
                else:
                    bot.send_message(chat_id=update.message.chat_id, text='Command blacklisted!')
            else:
                bot.send_message(chat_id=update.message.chat_id, text='Empty command')

    def checkBlacklist(self, cmd_string):
        if any(b_cmd.lower() in cmd_string.lower() for b_cmd in command_blacklist):
            return False
        else:
            return True

# HELP FUNCTION
    def helpHandler(self, bot, update):
            self.send_long_message(bot, update, self.help_text)

# MENU FUNCTIONS
    def build_menu(self, buttons, n_cols, header_buttons=None, footer_buttons=None):
            menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
            if header_buttons:
                menu.insert(0, header_buttons)
            if footer_buttons:
                menu.append(footer_buttons)
            return menu

    def menuHandler(self, bot, update):
            commands = ['/'+name for name in self.names]
            button_list = [KeyboardButton(s) for s in commands]
            reply_markup = ReplyKeyboardMarkup(self.build_menu(button_list, n_cols=2))
            bot.send_message(update.message.chat_id, "Menu", reply_markup=reply_markup)


#_______________________________________________________________________________________

def openConfigFile(filepath='config.ini'): # Open ConfigFile
    try:
        file=open(filepath)
        configFile=file.readlines()
        file.close()
        return configFile
    except:
        pass

if __name__ == '__main__':
    configFile=openConfigFile('/etc/telegramShell/config.ini')
    if configFile:
        telegramShell(configFile)
    else:
        print('**ERROR**\nconfig.ini not found!')
