"""
BMW lever control logic for BMW PiRacer Integrated Control System
"""

import time
from datetime import datetime
from constants import Constants
from data_models import BMWState
from logger import Logger

class BMWLeverController:
    """BMW lever control logic separated class"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.lever_position_map = {
            0x0E: 'Center',
            0x1E: 'Up (R)', 
            0x2E: 'Up+ (Beyond R)',
            0x3E: 'Down (D)',
            0x7E: 'Side (S)',
            0x5E: 'Manual Down (-)',
            0x6E: 'Manual Up (+)'
        }
        
        # Toggle control variables
        self.current_lever_position = 0x0E
        self.previous_lever_position = 0x0E
        self.lever_returned_to_center = True
        self.lever_returned_to_manual_center = True
        self.last_toggle_time = 0
        
    def decode_lever_message(self, msg, bmw_state: BMWState) -> bool:
        """Decode lever message"""
        if len(msg.data) < 4:
            return False
            
        try:
            crc = msg.data[0]
            counter = msg.data[1]
            lever_pos = msg.data[2]
            park_btn = msg.data[3]
            
            # Lever position mapping
            bmw_state.lever_position = self.lever_position_map.get(
                lever_pos, f'Unknown (0x{lever_pos:02X})'
            )
            
            # Button states
            bmw_state.park_button = 'Pressed' if (park_btn & 0x01) != 0 else 'Released'
            bmw_state.unlock_button = 'Pressed' if (park_btn & 0x02) != 0 else 'Released'
            
            # Toggle processing
            self.previous_lever_position = self.current_lever_position
            self.current_lever_position = lever_pos
            self._handle_toggle_action(lever_pos, park_btn, bmw_state)
            
            bmw_state.last_update = datetime.now().strftime("%H:%M:%S")
            return True
            
        except Exception as e:
            self.logger.error(f"Lever message decode error: {e}")
            return False
    
    def _handle_toggle_action(self, lever_pos: int, park_btn: int, bmw_state: BMWState):
        """Toggle-based gear switching processing"""
        current_time = time.time()
        unlock_pressed = (park_btn & 0x02) != 0
        
        # Unlock button processing
        if unlock_pressed and bmw_state.current_gear == 'P' and lever_pos == 0x0E:
            bmw_state.current_gear = 'N'
            self.logger.info("🔓 Unlock: PARK → NEUTRAL")
            return
        
        # Park button processing
        if (park_btn & 0x01) != 0 and lever_pos == 0x0E:
            bmw_state.current_gear = 'P'
            self.logger.info("🅿️ Park Button → PARK")
            return
        
        # Toggle timeout check
        if current_time - self.last_toggle_time < Constants.TOGGLE_TIMEOUT:
            return
        
        # Center return toggle processing
        if lever_pos == 0x0E and not self.lever_returned_to_center:
            self.lever_returned_to_center = True
            self._process_toggle_transition(bmw_state)
            self.last_toggle_time = current_time
        elif lever_pos != 0x0E:
            self.lever_returned_to_center = False

        # Manual center return toggle processing
        if lever_pos == 0x7E and not self.lever_returned_to_manual_center:
            self.lever_returned_to_manual_center = True
            self._process_toggle_manual_transition(bmw_state)
            self.last_toggle_time = current_time
        elif lever_pos != 0x7E:
            self.lever_returned_to_manual_center = False
    
    def _process_toggle_transition(self, bmw_state: BMWState):
        """Toggle transition processing"""
        transitions = {
            0x1E: self._handle_up_toggle,      # UP
            0x2E: lambda bs: self._set_gear(bs, 'P', "🎯 UP+ → PARK"),  # UP+
            0x3E: self._handle_down_toggle,    # DOWN
            0x7E: self._handle_side_toggle,    # SIDE
        }
        
        handler = transitions.get(self.previous_lever_position)
        if handler:
            handler(bmw_state)
    
    def _process_toggle_manual_transition(self, bmw_state: BMWState):
        """Manual toggle transition processing"""
        transitions = {
            0x5E: self._handle_manual_down_toggle,  # Manual Down
            0x6E: self._handle_manual_up_toggle,    # Manual Up
            0x0E: self._handle_side_toggle,         # Center → Side
        }
        
        handler = transitions.get(self.previous_lever_position)
        if handler:
            handler(bmw_state)
    
    def _handle_up_toggle(self, bmw_state: BMWState):
        """Up toggle processing"""
        gear_transitions = {
            'N': ('R', "🎯 N → REVERSE"),
            'D': ('N', "🎯 D → NEUTRAL"),
        }
        
        new_gear, msg = gear_transitions.get(bmw_state.current_gear, ('N', "🎯 UP → NEUTRAL"))
        self._set_gear(bmw_state, new_gear, msg)
    
    def _handle_down_toggle(self, bmw_state: BMWState):
        """Down toggle processing"""
        gear_transitions = {
            'N': ('D', "🎯 N → DRIVE"),
            'R': ('N', "🎯 R → NEUTRAL"),
        }
        
        new_gear, msg = gear_transitions.get(bmw_state.current_gear, ('D', "🎯 DOWN → DRIVE"))
        self._set_gear(bmw_state, new_gear, msg)
    
    def _handle_side_toggle(self, bmw_state: BMWState):
        """Side toggle processing"""
        if bmw_state.current_gear == 'D':
            bmw_state.manual_gear = 1
            self._set_gear(bmw_state, f'M{bmw_state.manual_gear}', f"🎯 D → MANUAL M{bmw_state.manual_gear}")
        elif bmw_state.current_gear.startswith('M'):
            self._set_gear(bmw_state, 'D', "🎯 Manual → DRIVE")
        else:
            self._set_gear(bmw_state, 'D', "🎯 SIDE → DRIVE")
    
    def _handle_manual_up_toggle(self, bmw_state: BMWState):
        """Manual up toggle processing"""
        if bmw_state.current_gear.startswith('M') and bmw_state.manual_gear < Constants.MANUAL_GEARS:
            bmw_state.manual_gear += 1
            self._set_gear(bmw_state, f'M{bmw_state.manual_gear}', f"🔼 Manual → M{bmw_state.manual_gear}")
    
    def _handle_manual_down_toggle(self, bmw_state: BMWState):
        """Manual down toggle processing"""
        if bmw_state.current_gear.startswith('M') and bmw_state.manual_gear > 1:
            bmw_state.manual_gear -= 1
            self._set_gear(bmw_state, f'M{bmw_state.manual_gear}', f"🔽 Manual → M{bmw_state.manual_gear}")
    
    def _set_gear(self, bmw_state: BMWState, gear: str, message: str):
        """Gear setting helper method"""
        bmw_state.current_gear = gear
        self.logger.info(message) 