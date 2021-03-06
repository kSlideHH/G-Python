import threading

from .gextension import Extension
from .hmessage import HMessage, Direction
from .hunityparsers import HUnityEntity, HUnityStatus


class UnityRoomUsers:
    def __init__(self, ext: Extension, users_in_room=28, get_guest_room=385, user_logged_out=29, status=34):
        self.room_users = {}
        self.__callback_new_users = None

        self.__ext = ext

        self.__lock = threading.Lock()

        ext.intercept(Direction.TO_CLIENT, self.__load_room_users, users_in_room)
        ext.intercept(Direction.TO_SERVER, self.__clear_room_users, get_guest_room)
        ext.intercept(Direction.TO_CLIENT, self.__remove_user, user_logged_out)
        ext.intercept(Direction.TO_CLIENT, self.__on_status, status)

    def __remove_user(self, message: HMessage):
        self.__start_remove_user_processing_thread(message.packet.read_int())

    def __start_remove_user_processing_thread(self, index: int):
        thread = threading.Thread(target=self.__process_remove_user, args=(index,))
        thread.start()

    def __process_remove_user(self, index: int):
        self.__lock.acquire()
        try:
            if index in self.room_users:
                del self.room_users[index]
        finally:
            self.__lock.release()

    def __load_room_users(self, message: HMessage):
        users = HUnityEntity.parse(message.packet)
        self.__start_user_processing_thread(users)

        if self.__callback_new_users is not None:
            self.__callback_new_users(users)

    def __process_users_in_room(self, entities):
        self.__lock.acquire()
        try:
            for user in entities:
                print(f'Adding entity {user}')
                self.room_users[user.index] = user
        finally:
            self.__lock.release()

    def __start_user_processing_thread(self, entities):
        thread = threading.Thread(target=self.__process_users_in_room, args=(entities,))
        thread.start()

    def __clear_room_users(self, _):
        self.__lock.acquire()
        self.room_users.clear()
        self.__lock.release()

    def on_new_users(self, func):
        self.__callback_new_users = func

    def __on_status(self, message):
        thread = threading.Thread(target=self.__parse_and_apply_updates, args=(message.packet,))
        thread.start()

    def __parse_and_apply_updates(self, packet):
        self.try_updates(HUnityStatus.parse(packet))

    def __apply_updates(self, updates):
        for update in updates:
            self.__lock.acquire()
            try:
                user = self.room_users[update.index]
                if isinstance(user, HUnityEntity):
                    user.try_update(update)
            except KeyError:
                pass
            finally:
                self.__lock.release()

    def __start_update_processing_thread(self, updates):
        thread = threading.Thread(target=self.__apply_updates, args=(updates,))
        thread.start()

    def try_updates(self, updates):
        self.__start_update_processing_thread(updates)
