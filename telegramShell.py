#!/usr/bin/python3 -u

import os
import sys
import time
import logging
from telegram.ext import CommandHandler, MessageHandler, Filters, Updater
from telegram import KeyboardButton, ReplyKeyboardMarkup, ChatAction, ParseMode
import subprocess
from threading import Thread
import json
import traceback

try:
    from PyQt5.QtCore import QCoreApplication

    translate = QCoreApplication.translate
except ImportError:
    def translate(id, text):
        return text


messageIntervall = 1

command_blacklist = [
    'nano ',
    'vi '
]

BACKBUTTON = translate('telegram', '..')

def first_lower(s):
    if len(s) == 0:
        return s
    else:
        return s[0].lower() + s[1:]


class bufferMessage(Thread):
    def __init__(self):
        self.lastbot = None
        self.lastupdate = None
        self.running = True
        self.buffer = ''
        Thread.__init__(self)

    def run(self):
        while self.running == True:
            if self.buffer != '':
                print(self.buffer)
                self.send_long_message(self.lastbot, self.lastupdate, self.buffer)
                self.buffer = ''
            else:
                time.sleep(messageIntervall)

    def addMessage(self, bot, update, message):
        self.lastbot = bot
        self.lastupdate = update
        self.buffer = self.buffer+'\n'+message

    def send_long_message(self, bot, update, message_text='Empty message'):
        restlength = len(message_text)
        while restlength > 0:
            bot.send_message(chat_id=update.message.chat_id, text=message_text)
            restlength = restlength-4096


class telegramShell():
    def __init__(self):
        self.load_config()
        self.load_clients()
        if self.config == {}:
            return False
        self.help_text = ''
        self.currentPath = os.path.dirname(os.path.abspath(__file__))

        self.updater = Updater(token=self.config['telegramToken'])
        self.bot = self.updater.bot
        self.dispatcher = self.updater.dispatcher
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
        self.sender = bufferMessage()
        self.sender.setName('buffer_sender')
        self.sender.start()

        if self.config['serverName'] != '':
            self.help_text = self.config['serverName']+'\n'
        for cmd in self.config['commands'].keys():
            self.addCmd(cmd, self.config['commands'][cmd]['info'],
                        self.config['commands'][cmd]['execute'])
        self.help_text = self.help_text + \
            '[shell] - Simply type shell commands\n/shortcuts - Show commands\n/help - Command-List'

        echo_handler = MessageHandler(Filters.text, self.shellMessageHandler)
        self.dispatcher.add_handler(echo_handler)
        start_handler = CommandHandler('start', self.helpHandler)
        self.dispatcher.add_handler(start_handler)
        help_handler = CommandHandler('help', self.helpHandler)
        self.dispatcher.add_handler(help_handler)
        menu_handler = CommandHandler('shortcuts', self.shortcutHandler)
        self.dispatcher.add_handler(menu_handler)
        file_handler = MessageHandler(Filters.document, self.fileHandler)
        self.dispatcher.add_handler(file_handler)
        self.updater.start_polling()
        print('Telegram-Server successfully started!')
        self.updater.idle()
        print('Telegram-Server stopped!')
        self.sender.running = False
        self.updater.stop()

    def getLineContent(self, line):  # Returns values in '' out of a String
        start = line.find("'")+1
        end = line.find("'", start)
        print(line[start:end])
        return line[start:end]

    def addCmd(self, name, info, command):  # Create CommandHandler and add to dispatcher
        def cmd(bot, update):
            bot.send_chat_action(chat_id=update.message.chat_id, action=ChatAction.TYPING)
            self.exec_command(bot, update, command)
        handler = CommandHandler(name, cmd)
        self.help_text = self.help_text+'/'+name+' - '+info+'\n'
        self.dispatcher.add_handler(handler)

    def exec_command(self, bot, update, cmd_str):
        print('CMD: '+cmd_str)
        shellEnd = 0
        if cmd_str.find('partialCMD') == 0:
            filepath = os.path.dirname(os.path.abspath(__file__))
            partialCMDpath = os.path.join(filepath, 'partialCMD.py')
            cmd_str = 'python3 '+partialCMDpath+' '+cmd_str.replace('partialCMD', '')
            print(cmd_str)
        if cmd_str == 'll':
            cmd_str = 'ls -laF'
        if cmd_str.find('cd ') == 0:
            self.changeDirectory(bot, update, cmd_str[3:])
        else:
            cmd = subprocess.Popen(cmd_str, shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
            # for line in cmd.stdout.readline():
            for line in iter(cmd.stdout.readline, ''):
                line = line.decode('utf-8').replace('\r', '').replace('\n', '')
                print(line)
                #self.send_long_message(bot, update, line)
                if line != '':
                    self.sender.addMessage(bot, update, line)
                sys.stdout.flush()
                if line == '':
                    shellEnd = shellEnd+1
                    if shellEnd > 2:
                        path = subprocess.Popen('pwd -P', shell=True, stdout=subprocess.PIPE)
                        path = path.stdout.readline().decode('utf-8')
                        path = path.replace('\r', '').replace('\n', '')
                        print('shell:'+path+'$')
                        #self.send_long_message(bot, update, 'shell:'+path+'$')
                        self.sender.addMessage(bot, update, 'shell:'+path+'$')
                        break
                else:
                    shellEnd = 0

    def changeDirectory(self, bot, update, dir):
        try:
            os.chdir(dir)
            path = os.getcwd()
            #path = subprocess.Popen('pwd -P', shell=True, stdout=subprocess.PIPE)
            #path = path.stdout.readline().decode('utf-8')
            #path = path.replace('\r', '').replace('\n', '')
            #text = ''
        except Exception:
            path = os.getcwd()
            #text = 'No such directory\n'
            #path = subprocess.Popen('pwd -P', shell=True, stdout=subprocess.PIPE)
            #path = path.stdout.readline().decode('utf-8')
        #path = path.replace('\r', '').replace('\n', '')
            #self.sender.addMessage(bot, update, 'shell:'+path+'$')
            pass

        if path.startswith('d\\'):
            path = path.replace('d\\','D:\\')
        self.currentPath = path
        text = 'shell: '+self.currentPath+' $ '
        dirList = self.currentDir()
        self.sendMenuMessage(bot, update, dirList, text=text, n_cols=1, backButton=True)

    def currentDir(self):
        return os.listdir(self.currentPath)

    def fileHandler(self, bot, update):
        if self.permissionHandler(bot, update):
            file = bot.getFile(update.message.document.file_id)
            file.download(os.path.join(self.currentPath, str(update.message.document.file_name)))
            self.send_message(update.message.chat_id, text="File uploaded successfully")
            self.changeDirectory(bot, update, '')

#################### Action Handler #################################################
    def permissionHandler(self, bot, update):
        if str(update.message.chat_id) in self.clients.keys():
            return True
        elif self.clients == {}:
            self.clients[str(update.message.chat_id)] = {'admin': True, 'read': True, 'write': True, 'console': True}
            self.send_message(chat_id=update.message.chat_id, text='You are the first one connecting to this bot!\nSo from now on, you will be the Administator!')
            self.save_clients()
            return False
        else:
            self.send_message(chat_id=update.message.chat_id, text='You do not have the permission for this bot!\nAdministator has been informed!')
            for chat_id in self.clients.keys():
                if self.clients[chat_id]['admin'] == True:
                    self.send_message(chat_id=chat_id, text='Unauthorized connection to your bot was prohibited (Chat-ID: '+str(update.message.chat_id)+'). Do you want to allow this client to connect with your bot?')
            return False


    def downloadFile(self, bot, update, filename):
        bot.send_chat_action(chat_id=update.message.chat_id,
                                     action=ChatAction.UPLOAD_DOCUMENT)
        dir = os.path.join(self.currentPath, filename)
        bot.send_document(chat_id=update.message.chat_id, document=open(
                    dir, 'rb'))
# SHELL HANDLER
    def shellMessageHandler(self, bot, update):
        if self.permissionHandler(bot, update):
            if self.clients[str(update.message.chat_id)]['console'] is True:
                cmd_string = update.message.text
                if cmd_string in self.currentDir() or cmd_string == BACKBUTTON:
                    if os.path.isfile(cmd_string):
                        self.downloadFile(bot, update, cmd_string)
                    else:
                        self.changeDirectory(bot, update, cmd_string)
                elif cmd_string and cmd_string != "":
                    if self.checkBlacklist(cmd_string) == True:
                        self.exec_command(bot, update, first_lower(cmd_string))
                        text = 'shell: '+self.currentPath+' $ '
                        dirList = self.currentDir()
                        self.sendMenuMessage(bot, update, dirList, text=text, n_cols=1, backButton=True)
                    else:
                        self.send_message(chat_id=update.message.chat_id, text='Command blacklisted!')
                else:
                    self.send_message(chat_id=update.message.chat_id, text='Empty command')
            else:
                self.send_message(chat_id=update.message.chat_id, text='Sorry, you don\'t have the Permission to use the console.')


    def checkBlacklist(self, cmd_string):
        if any(b_cmd.lower() in cmd_string.lower() for b_cmd in command_blacklist):
            return False
        else:
            return True

# HELP FUNCTION
    def helpHandler(self, bot, update):
        if self.permissionHandler(bot, update):
            self.sender.addMessage(bot, update, self.help_text)

# MENU FUNCTIONS
    def build_menu(self, buttons, n_cols, header_buttons=None, footer_buttons=None):
        menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
        if header_buttons:
            menu.insert(0, header_buttons)
        if footer_buttons:
            menu.append(footer_buttons)
        return menu

    def shortcutHandler(self, bot, update):
        if self.permissionHandler(bot, update):
            commands = ['/'+name for name in self.config['commands'].keys()]
            self.sendMenuMessage(bot, update, commands, "Menu", '', 1, False)

    def send_message(self, chat_id, text, parse_mode=ParseMode.MARKDOWN, disable_notification=True, delete=False):
        try:
            lastMessage = self.bot.send_message(
                chat_id, text=text, disable_notification=True, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            print(traceback.format_exc())
            lastMessage = self.bot.send_message(
                chat_id, text=text, disable_notification=True)
        # if chat_id not in self.last_messages.keys():
        #     self.last_messages[chat_id] = [lastMessage.message_id]
        #
        # if delete:
        #     self.last_messages[chat_id].append(lastMessage.message_id)
        # if len(self.last_messages[chat_id]) > 3:
        #     message_id = self.last_messages[chat_id].pop(0)
        #     self.bot.delete_message(chat_id, message_id)

    def sendMenuMessage(self, bot, update, buttonlist, text='', description_text='', n_cols=1, backButton=True):
        try:
            chat_id = update.message.chat_id
        except Exception:
            chat_id = update
        button_list = []
        if backButton:
            button_list.append(BACKBUTTON)
        button_list.append('/help')
        button_list.append('/shortcuts')
        button_list += [KeyboardButton(s) for s in buttonlist]
        reply_markup = ReplyKeyboardMarkup(self.build_menu(button_list, n_cols=n_cols))

        if description_text != '':
            text = description_text.replace('/n', '/n') + '\n' + text

        try:
            lastMessage = self.bot.send_message(
                chat_id, text=text, reply_markup=reply_markup, disable_notification=True, parse_mode=ParseMode.MARKDOWN,)
        except Exception:
            lastMessage = self.bot.send_message(
                chat_id, text=text, reply_markup=reply_markup, disable_notification=True)
        # if chat_id not in self.last_messages.keys():
        #     self.last_messages[chat_id] = [lastMessage.message_id]
        # else:
        #     self.last_messages[chat_id].append(lastMessage.message_id)
        #     if len(self.last_messages[chat_id]) > 3:
        #         message_id = self.last_messages[chat_id].pop(0)
        #         try:
        #             self.bot.delete_message(chat_id, message_id)
        #         except Exception:
        #             pass

    def load_clients(self):
        filepath = os.path.dirname(os.path.abspath(__file__))
        configpath = os.path.join(filepath, 'clients.json')
        if os.path.exists(configpath):
            try:
                with open(configpath, encoding="UTF-8") as jsonfile:
                    self.clients = json.load(jsonfile, encoding="UTF-8")
            except:
                self.clients = {}
        else:
            self.clients = {}

    def save_clients(self):
        filepath = os.path.dirname(os.path.abspath(__file__))
        configpath = os.path.join(filepath, 'clients.json')
        with open(configpath, 'w', encoding="utf-8") as fp:
            json.dump(self.clients, fp,  sort_keys=False, indent=4, separators=(',', ': '))

    def load_config(self):
        filepath = os.path.dirname(os.path.abspath(__file__))
        configpath = os.path.join(filepath, 'config.json')
        if os.path.exists(configpath):
            try:
                with open(configpath, encoding="UTF-8") as jsonfile:
                    self.config = json.load(jsonfile, encoding="UTF-8")
            except:
                self.config = {}
        else:
            self.config = {}

    def save_config(self):
        filepath = os.path.dirname(os.path.abspath(__file__))
        configpath = os.path.join(filepath, 'config.json')
        with open(configpath, 'w', encoding="utf-8") as fp:
            json.dump(self.config, fp,  sort_keys=False, indent=4, separators=(',', ': '))


if __name__ == '__main__':
    telegramShell()
