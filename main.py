#aaa
import asyncio
from bleak import BleakClient, BleakScanner
import time
import math
from threading import Thread

class DualShock4Controller:
    ANALOG_CENTER = 128
    MAX_ANALOG_VAL = 127
    DEADZONE = 20
    LEVEL = 1

    def __init__(self, loop):
        self.LeftStickY = 0
        self.RightStickY = 0
        self.CirclePressed = False
        self.ExitPressed = False
        self.SlowModeActive = False 
        self.SuperSlowModeActive = False 
        self.is_split_mode = False
        self.loop = loop
        self._monitor_thread = Thread(target=self._monitor_controller, daemon=True)
        self._monitor_thread.start()

    def _notify_jumplevel(self):
        t = self.LEVEL * 20
        self.loop.call_soon_threadsafe(print, f"Current jump time is {t}ms")

    def _notify_drive_mode(self):
        mode_text = "分割モード (左右のスティックで独立操作)" if self.is_split_mode else "通常モード (左スティックで両輪操作)"
        self.loop.call_soon_threadsafe(print, f"[Mode Change] {mode_text}")

    def _monitor_controller(self):
        while not self.ExitPressed:
            try:
                from inputs import get_gamepad
                events = get_gamepad()
            except Exception:
                self.LeftStickY, self.RightStickY = 0, 0
                time.sleep(1)
                continue
            
            for event in events:
                if event.code == 'BTN_TL':
                    if event.state == 1:
                        self.SlowModeActive = True
                    elif event.state == 0:
                        self.SlowModeActive = False
                elif event.code == 'BTN_TL2':
                    if event.state == 1:
                        self.SuperSlowModeActive = True
                    elif event.state == 0:
                        self.SuperSlowModeActive = False
                elif event.code == 'ABS_Y':
                    self.LeftStickY = -(event.state - self.ANALOG_CENTER)
                elif event.code == 'ABS_RY':
                    self.RightStickY = -(event.state - self.ANALOG_CENTER)
                elif event.code == 'BTN_TR' and event.state == 1:
                    self.CirclePressed = True
                elif event.code == "ABS_HAT0Y" and event.state == -1:
                    self.LEVEL = min(10, self.LEVEL + 1)
                    self._notify_jumplevel()
                elif event.code == "ABS_HAT0Y" and event.state == 1:
                    self.LEVEL = max(1, self.LEVEL - 1)
                    self._notify_jumplevel()
                elif event.code == "ABS_HAT0X" and (event.state == -1 or event.state == 1):
                    self.is_split_mode = not self.is_split_mode
                    self._notify_drive_mode()

    def get_motor_speeds(self):
        left = 0 if abs(self.LeftStickY) < self.DEADZONE else self.LeftStickY
        right = 0 if abs(self.RightStickY) < self.DEADZONE else self.RightStickY
        left_pwm = int((left / self.MAX_ANALOG_VAL) * 255)
        right_pwm = int((right / self.MAX_ANALOG_VAL) * 255)
        left_pwm = max(-255, min(255, left_pwm))
        right_pwm = max(-255, min(255, right_pwm))

        if not self.is_split_mode:
            right_pwm = left_pwm

        if self.SlowModeActive:
            left_pwm = int(left_pwm * 3 / 4)
            right_pwm = int(right_pwm * 3 / 4)
        elif self.SuperSlowModeActive:
            left_pwm = int(left_pwm / 2)
            right_pwm = int(right_pwm / 2)

        return left_pwm, right_pwm

    def get_jumplevel(self):
        return self.LEVEL

    def jump(self):
        if self.CirclePressed:
            self.CirclePressed = False
            return True
        return False

    def should_exit(self):
        return self.ExitPressed

# --- BLE設定 ---
DEVICE_NAME = "ESP32_BLE_MAKAIZO"
SERVICE_UUID = "12345678-1234-1234-1234-1234567890ab"
CHARACTERISTIC_UUID = "abcdefab-1234-5678-1234-abcdefabcdef"

# --- メインロジック ---
async def find_device_address(name: str):
    print("BLE デバイスをスキャン中…")
    devices = await BleakScanner.discover(timeout=10)
    for d in devices:
        if d.name == name:
            print(f"見つかったデバイス: {d.name} ({d.address})")
            return d.address
    print("指定したデバイスが見つかりませんでした。")
    return None

async def run_client(address: str, controller: DualShock4Controller):
    async with BleakClient(address) as client:
        print("BLE 接続完了:", address)
        print("左右スティックで操作,Rでジャンプ, L長押しで低速化.")

        prev_command = ""
        while not controller.should_exit():
            left_motor, right_motor = controller.get_motor_speeds()
            command = f"M,{left_motor},{right_motor}"

            if command != prev_command:
                await client.write_gatt_char(CHARACTERISTIC_UUID, command.encode())
                print(f"[BLE] 送信: {command}")
                prev_command = command

            if controller.jump():
                level = controller.get_jumplevel()
                jump_command = f"J,{level}"
                await client.write_gatt_char(CHARACTERISTIC_UUID, jump_command.encode())
                print(f"[BLE] 送信: {jump_command}")

            await asyncio.sleep(0.05)
    print("\n[BLE] プログラムを終了します。")


async def main():
    address = await find_device_address(DEVICE_NAME)
    if address is None:
        return
    
    loop = asyncio.get_running_loop()
    controller = DualShock4Controller(loop=loop)
    
    await run_client(address, controller)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ImportError:
        print("ライブラリ 'inputs' が見つかりません。 pip install inputs でインストールしてください。")
    except Exception as e:
        print(f"エラーが発生しました: {e}")

