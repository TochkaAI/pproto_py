from threading import Thread

from .badSituations import UnknownCommandRecieved
from .commandList import CommandList
from .logger import write_info
from . import baseCommands
from . import baseCommandsImpl
from .baseCommandsImpl import ProtocolCompatibleCommand, CloseConnectionCommand, UnknownCommand
from .connectionPool import ConnectionPool
from .message import Message


class TcpWorker:
    """Главная сущность осуществляющая основную логику общения между клиентами в рамках оговоренного протокола"""
    user_commands_list: CommandList
    base_commands_list: CommandList

    def __init__(self, ip, port, client_commands, client_command_impl):
        self.ip = ip
        self.port = port

        self.connection_pool = ConnectionPool()
        self.disconnection_handler = None

        self.base_commands_list = CommandList(baseCommands, baseCommandsImpl)
        self.user_commands_list = CommandList(client_commands, client_command_impl)

        self.unknown_command_list = []

    def _set_disconnection_handler(self, handler):
        """если пользователь пожилает задать обработчик на разрыв соеднинения то присвоем его значение тут"""
        self.disconnection_handler = handler

    def _cmd_method_creator(self, connection):
        for cmd in list(self.user_commands_list.values()) + list(self.base_commands_list.values()):
            setattr(connection, cmd[0] + '_exec', cmd[2].exec_decorator(connection))
            setattr(connection, cmd[0] + '_sync', cmd[2].sync_decorator(connection))
            setattr(connection, cmd[0] + '_async', cmd[2].async_decorator(connection))

    def get_command_name(self, commandUuid):
        """По UUID команды получаем Имя команды из списка базовых или из списка пользовательских"""
        return self.base_commands_list.get_command_name(commandUuid) or \
               self.user_commands_list.get_command_name(commandUuid)

    def command_handler(self, msg):
        if msg.get_command() in self.base_commands_list:
            """обработки базовых команд"""
            command = self.base_commands_list.get_command_impl(msg.get_command())
        else:
            """обработка пользовательских команд"""
            command = self.user_commands_list.get_command_impl(msg.get_command())
        # и теперь закинем обрабатывать это в отдельный поток, чтоб не стопорило получение новых команд
        thread = Thread(target=command.handler, args=(msg,))
        thread.daemon = True
        thread.start()

    def start_listening(self, connection):
        """эта команда для конекции запускает бесконечный цикл прослушивания сокета"""
        thread = Thread(target=self.command_listener, args=(connection,))
        thread.daemon = True
        thread.start()

    def command_listener(self, connection):
        """метод запускается в отдельном потоке и мониторит входящие пакеты
        пытается их распарсить и выполнить их соответсвующу обработку"""
        while True:
            answer = connection.mrecv()
            if answer:
                write_info(f'[{connection.getpeername()}] Msg JSON receeved: {answer}')
                try:
                    msg = Message.from_string(connection, answer)
                except UnknownCommandRecieved:
                    write_info(f'[{connection.getpeername()}] Unknown msg received')
                    connection.exec_command(UnknownCommand, answer)
                else:
                    write_info(f'[{connection.getpeername()}] Msg received: {msg}')
                    # Это команда с той стороны, её нужно прям тут и обработать!
                    if msg.get_id() not in connection.request_pool:
                        self.command_handler(msg)
                    # Это ответы, который нужно обработать
                    else:
                        connection.message_pool.add_message(msg)
            else:
                break
        # соответственно если я тут, значит у нас произошёл разрыв соединения
        self.connection_pool.del_connection(connection)
        if connection.is_connected():  # тут нужна проверка, потому что мы сами могли порвать соединение
            connection.close()
            if self.disconnection_handler is not None:
                self.disconnection_handler(connection)

    def start(self, connection):
        """функция которая выполняет стандартный сценарий, сразу после образования Tcp соединения"""
        self.connection_pool.add_connection(connection)
        ''' После установки TCP соединения клиент отправляет на сокет сервера 16 байт (обычный uuid).
                    Это сигнатура протокола. Строковое представление сигнатуры для json формата: "fea6b958-dafb-4f5c-b620-fe0aafbd47e2".
                    Если сервер присылает назад этот же uuid, то все ОК - можно работать'''
        connection.send_hello()
        ''' После того как сигнатуры протокола проверены клиент и сервер отправляют друг другу первое сообщение - 
            ProtocolCompatible.'''
        connection.exec_command_async(ProtocolCompatibleCommand)
        self.start_listening(connection)

    def finish_all(self, code, description):
        """функция завершает все соединения предварительно отправив команду CloseConnection"""
        for conn in self.connection_pool.values():
            perr_name = conn.getpeername()
            conn.exec_command_sync(CloseConnectionCommand, code, description)
            conn.close()
            write_info(f'[{perr_name}] Disconect from host')