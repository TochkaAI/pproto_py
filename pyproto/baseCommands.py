"""
Список констант с базовыми командами
"""
import sys

from .message import Message
from .logger import write_info


Unknown = "UNKNOWN"
Error = "ERROR"
ProtocolCompatible = "PROTOCOL_COMPATIBLE"
CloseConnection = "CLOSE_CONNECTION"


# Функция регистрирует внутри модуля переменные с именем описанным выше,
# для удобного пользования в дальнейшем
def REGISTRY_COMMAND(name, uuid):
    setattr(sys.modules[__name__], name, uuid)


# Регистрация базовых команд
REGISTRY_COMMAND(Unknown,            "4aef29d6-5b1a-4323-8655-ef0d4f1bb79d")
REGISTRY_COMMAND(Error,              "b18b98cc-b026-4bfe-8e33-e7afebfbe78b")
REGISTRY_COMMAND(ProtocolCompatible, "173cbbeb-1d81-4e01-bf3c-5d06f9c878c3")
REGISTRY_COMMAND(CloseConnection,    "e71921fd-e5b3-4f9b-8be7-283e8bb2a531")


class BaseCommand:
    """
    Шаблон реализации всех команд
    Чтобы зарегистрировать в воркере свою команду, необходимо наследоваться от этого класса и
    реализовать необходимые команды.
    Пример реализации расположен в файле baseCommandsImpl, где с помощью этого класса реализованы
    базовые команды протокола
    """
    COMMAND_UUID = None
    @staticmethod
    def initial(connection, *args, **kwargs):
        """
        Метод вызывается перед отправкой любой команды, он должен вернуть сформированный message
        для последующей отправки
        """
        raise NotImplemented('Initialization method not implemented yet')

    @staticmethod
    def answer(msg: Message):
        """
        Метод обработчик, срабатывает в случае, когда на команду приходит ответ, с тем же идентификатором.
        Сюда мы можем попасть с сообщение типа Command и Answer
        """
        pass

    @staticmethod
    def handler(msg: Message):
        """
        Метод обработчик входящей команды, идентификатор которой не найден в списке запросов.
        Скорее всего это значит что вторая сторона, отправила команду, но также сюда можно попасть по какой-либо ошибке.
        Так же как и в обработчике answer сюда можно попасть с типом и Command и Answer
        """
        raise Exception('Message processing method not implemented yet')

    @staticmethod
    def unknown(msg: Message):
        """
        Обработчик ситуации, при которой в ответ на команду приходит сообщение о том, что данная команда неизвестна
        """
        write_info(f'[{msg.my_connection.getpeername()}] Unknown command for remote client! {msg.get_id()}')
        # raise Exception('Команда неизвестна для удалённого клиента!')

    @staticmethod
    def timeout(msg: Message):
        """
        Если в сообщении задать максимальное время выполнения команды,
        в случае истечения времени сработает этот обработчик
        """
        raise Exception('Waiting command execution timed out')

    @classmethod
    def exec_decorator(cls, connection):
        def function_template(*args, **kwargs):
            connection.exec_command(cls, *args, **kwargs)
        return function_template

    @classmethod
    def sync_decorator(cls, connection):
        def function_template(*args, **kwargs):
            return connection.exec_command_sync(cls, *args, **kwargs)
        return function_template

    @classmethod
    def async_decorator(cls, connection):
        def function_template(*args, **kwargs):
            connection.exec_command_async(cls, *args, **kwargs)
        return function_template
