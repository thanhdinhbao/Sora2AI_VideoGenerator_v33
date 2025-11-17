#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sora2 Character Manager
=======================
Manages character database with JSON storage
Stores: username, thumbnail_path, character_id, cameo_id, profile_url

Author: Trần Nguyên - Zalo: 0789.535.888
"""

import os
import json
import logging
import shutil
from typing import List, Dict, Optional, Tuple  # ← FIX: Thêm Tuple vào đây
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class Sora2CharacterManager:
    """Manager for Sora2 character database"""
    
    def __init__(self, db_path: str = "sora2_characters.json", thumbnails_dir: str = "sora2_character_thumbnails"):
        """
        Initialize character manager
        
        Args:
            db_path: Path to JSON database file
            thumbnails_dir: Directory to store character thumbnails
        """
        self.db_path = db_path
        self.thumbnails_dir = thumbnails_dir
        self.characters = {}
        
        # Create thumbnails directory
        os.makedirs(self.thumbnails_dir, exist_ok=True)
        
        # Load existing data
        self.load()
    
    def load(self) -> bool:
        """Load character database from JSON file"""
        if not os.path.exists(self.db_path):
            logger.info(f"[CHARACTER MANAGER] Database not found, creating new: {self.db_path}")
            self.characters = {}
            self.save()
            return True
        
        try:
            with open(self.db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.characters = data.get('characters', {})
            
            logger.info(f"[CHARACTER MANAGER] ✅ Loaded {len(self.characters)} characters")
            return True
            
        except Exception as e:
            logger.error(f"[CHARACTER MANAGER] ❌ Load error: {e}", exc_info=True)
            self.characters = {}
            return False
    
    def save(self) -> bool:
        """Save character database to JSON file"""
        try:
            data = {
                'version': '1.0',
                'last_updated': datetime.now().isoformat(),
                'total_characters': len(self.characters),
                'characters': self.characters
            }
            
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[CHARACTER MANAGER] ✅ Saved {len(self.characters)} characters")
            return True
            
        except Exception as e:
            logger.error(f"[CHARACTER MANAGER] ❌ Save error: {e}", exc_info=True)
            return False
    
    def add_character(
        self,
        character_id: str,
        cameo_id: str,
        username: str,
        display_name: str,
        profile_url: str,
        thumbnail_url: str,
        thumbnail_source_path: str = None,
        generation_id: str = None,
        visibility: str = "public",
        instruction_text: str = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Add a character to database
        
        Args:
            character_id: Character ID from Sora2
            cameo_id: Cameo ID
            username: Username
            display_name: Display name
            profile_url: Profile URL on Sora2
            thumbnail_url: Thumbnail URL from Sora2
            thumbnail_source_path: Local path to thumbnail (will be copied)
            generation_id: Original generation ID
            visibility: 'public' or 'private'
            instruction_text: Character instructions
        
        Returns:
            (success, error_message)
        """
        try:
            # Check if character already exists
            if character_id in self.characters:
                logger.warning(f"[CHARACTER MANAGER] Character already exists: {username}")
                return False, f"Character already exists: {username}"
            
            # Copy thumbnail to local storage
            local_thumbnail_path = None
            if thumbnail_source_path and os.path.exists(thumbnail_source_path):
                # Generate unique filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                ext = os.path.splitext(thumbnail_source_path)[1]
                filename = f"{username}_{timestamp}{ext}"
                local_thumbnail_path = os.path.join(self.thumbnails_dir, filename)
                
                # Copy file
                shutil.copy2(thumbnail_source_path, local_thumbnail_path)
                logger.info(f"[CHARACTER MANAGER] Thumbnail copied: {filename}")
            
            # Create character entry
            character_data = {
                'character_id': character_id,
                'cameo_id': cameo_id,
                'username': username,
                'display_name': display_name,
                'profile_url': profile_url,
                'thumbnail_url': thumbnail_url,
                'thumbnail_local_path': local_thumbnail_path,
                'generation_id': generation_id,
                'visibility': visibility,
                'instruction_text': instruction_text,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Add to database
            self.characters[character_id] = character_data
            
            # Save to file
            if self.save():
                logger.info(f"[CHARACTER MANAGER] ✅ Character added: {username}")
                return True, None
            else:
                return False, "Failed to save database"
            
        except Exception as e:
            logger.error(f"[CHARACTER MANAGER] ❌ Add character error: {e}", exc_info=True)
            return False, str(e)
    
    def get_character(self, character_id: str) -> Optional[Dict]:
        """Get character by ID"""
        return self.characters.get(character_id)
    
    def get_character_by_username(self, username: str) -> Optional[Dict]:
        """Get character by username"""
        for char_id, char_data in self.characters.items():
            if char_data['username'].lower() == username.lower():
                return char_data
        return None
    
    def delete_character(self, character_id: str) -> Tuple[bool, Optional[str]]:
        """
        Delete a character
        
        Args:
            character_id: Character ID to delete
        
        Returns:
            (success, error_message)
        """
        try:
            if character_id not in self.characters:
                return False, "Character not found"
            
            char_data = self.characters[character_id]
            username = char_data['username']
            
            # Delete local thumbnail if exists
            local_thumbnail = char_data.get('thumbnail_local_path')
            if local_thumbnail and os.path.exists(local_thumbnail):
                try:
                    os.remove(local_thumbnail)
                    logger.info(f"[CHARACTER MANAGER] Thumbnail deleted: {os.path.basename(local_thumbnail)}")
                except Exception as e:
                    logger.warning(f"[CHARACTER MANAGER] Failed to delete thumbnail: {e}")
            
            # Remove from database
            del self.characters[character_id]
            
            # Save
            if self.save():
                logger.info(f"[CHARACTER MANAGER] ✅ Character deleted: {username}")
                return True, None
            else:
                return False, "Failed to save database"
            
        except Exception as e:
            logger.error(f"[CHARACTER MANAGER] ❌ Delete error: {e}", exc_info=True)
            return False, str(e)
    
    def update_character(self, character_id: str, **kwargs) -> Tuple[bool, Optional[str]]:
        """
        Update character data
        
        Args:
            character_id: Character ID
            **kwargs: Fields to update
        
        Returns:
            (success, error_message)
        """
        try:
            if character_id not in self.characters:
                return False, "Character not found"
            
            # Update fields
            for key, value in kwargs.items():
                if key in self.characters[character_id]:
                    self.characters[character_id][key] = value
            
            # Update timestamp
            self.characters[character_id]['updated_at'] = datetime.now().isoformat()
            
            # Save
            if self.save():
                logger.info(f"[CHARACTER MANAGER] ✅ Character updated: {character_id}")
                return True, None
            else:
                return False, "Failed to save database"
            
        except Exception as e:
            logger.error(f"[CHARACTER MANAGER] ❌ Update error: {e}", exc_info=True)
            return False, str(e)
    
    def list_all(self) -> List[Dict]:
        """
        List all characters
        
        Returns:
            List of character data dictionaries
        """
        return sorted(
            self.characters.values(),
            key=lambda x: x.get('created_at', ''),
            reverse=True
        )
    
    def search(self, keyword: str) -> List[Dict]:
        """
        Search characters by keyword
        
        Args:
            keyword: Search keyword (username or display_name)
        
        Returns:
            List of matching characters
        """
        keyword = keyword.lower()
        results = []
        
        for char_data in self.characters.values():
            if (keyword in char_data['username'].lower() or
                keyword in char_data.get('display_name', '').lower() or
                keyword in char_data.get('instruction_text', '').lower()):
                results.append(char_data)
        
        return sorted(
            results,
            key=lambda x: x.get('created_at', ''),
            reverse=True
        )
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        return {
            'total': len(self.characters),
            'public': sum(1 for c in self.characters.values() if c.get('visibility') == 'public'),
            'private': sum(1 for c in self.characters.values() if c.get('visibility') == 'private'),
            'with_instructions': sum(1 for c in self.characters.values() if c.get('instruction_text')),
            'thumbnails_dir_size': self._get_dir_size(self.thumbnails_dir)
        }
    
    def _get_dir_size(self, path: str) -> str:
        """Get directory size in human-readable format"""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total_size += os.path.getsize(fp)
            
            # Convert to MB
            size_mb = total_size / (1024 * 1024)
            return f"{size_mb:.2f} MB"
        except:
            return "N/A"
    
    def export_to_json(self, output_path: str) -> Tuple[bool, Optional[str]]:
        """Export database to custom JSON file"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.characters, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[CHARACTER MANAGER] ✅ Exported to: {output_path}")
            return True, None
            
        except Exception as e:
            logger.error(f"[CHARACTER MANAGER] ❌ Export error: {e}", exc_info=True)
            return False, str(e)
    
    def import_from_json(self, input_path: str, merge: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Import characters from JSON file
        
        Args:
            input_path: Path to JSON file
            merge: If True, merge with existing data. If False, replace all.
        
        Returns:
            (success, error_message)
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            if not merge:
                self.characters = import_data
            else:
                self.characters.update(import_data)
            
            if self.save():
                count = len(import_data)
                logger.info(f"[CHARACTER MANAGER] ✅ Imported {count} characters")
                return True, None
            else:
                return False, "Failed to save after import"
            
        except Exception as e:
            logger.error(f"[CHARACTER MANAGER] ❌ Import error: {e}", exc_info=True)
            return False, str(e)


if __name__ == "__main__":
    # Test
    print("Sora2 Character Manager")
    print("=" * 50)
    
    manager = Sora2CharacterManager()
    print(f"\n✅ Manager initialized")
    print(f"Database: {manager.db_path}")
    print(f"Thumbnails: {manager.thumbnails_dir}")
    
    stats = manager.get_stats()
    print(f"\n📊 Stats: {stats}")
    
    characters = manager.list_all()
    print(f"\n👥 Characters: {len(characters)}")
    for char in characters:
        print(f"  - {char['username']} ({char['display_name']})")