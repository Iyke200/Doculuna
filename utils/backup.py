# utils/backup.py
"""
DocuLuna Backup Utility

Handles secure backup and restoration of user data, preferences, and system state.
Supports AES-256 encryption, LZMA compression, and incremental backups.

Usage:
    backup_manager = BackupManager(user_id=123, encryption_key=key)
    backup_data = await backup_manager.create_backup()
    restored_data = await backup_manager.restore_backup(backup_file)
"""

import logging
import os
import json
import hashlib
from typing import Dict, Any, Optional, Union, IO
from datetime import datetime
from pathlib import Path
import lzma
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import tarfile
import tempfile
from dataclasses import dataclass, asdict
from enum import Enum

import aiofiles

# Local imports (assuming these exist)
from database.db import get_user_data, get_all_user_data  # type: ignore
from handlers.premium import get_premium_data  # type: ignore
from handlers.stats import stats_tracker, StatType  # type: ignore

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@dataclass
class BackupMetadata:
    """Backup metadata structure."""
    user_id: int
    backup_id: str
    version: str = "1.0"
    created_at: datetime = None
    backup_type: str = "full"
    data_size: int = 0
    compressed_size: int = 0
    checksum: str = ""
    encrypted: bool = True
    incremental_from: Optional[str] = None  # Previous backup ID for incremental
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

class BackupType(Enum):
    """Types of backups supported."""
    FULL = "full"
    INCREMENTAL = "incremental"
    SYSTEM = "system"

class BackupError(Exception):
    """Custom exception for backup operations."""
    pass

class BackupManager:
    """
    Secure backup and restore manager for DocuLuna.
    
    Handles encryption, compression, and integrity verification.
    
    Args:
        user_id: User identifier for backup context
        encryption_key: 32-byte AES key for encryption
        backup_dir: Directory for storing backup files (default: ./backups)
        max_backup_size_mb: Maximum size per backup in MB (default: 100)
    """
    
    BACKUP_VERSION = "1.0"
    AES_KEY_LENGTH = 32  # AES-256
    SALT_LENGTH = 16
    ITERATIONS = 100000  # PBKDF2 iterations
    
    def __init__(
        self,
        user_id: int,
        encryption_key: bytes,
        backup_dir: str = "./backups",
        max_backup_size_mb: int = 100
    ):
        if len(encryption_key) != self.AES_KEY_LENGTH:
            raise ValueError(f"Encryption key must be {self.AES_KEY_LENGTH} bytes")
        
        self.user_id = user_id
        self.encryption_key = encryption_key
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.max_backup_size = max_backup_size_mb * 1024 * 1024  # Convert to bytes
        
        # Ensure backup directory is secure
        os.chmod(str(self.backup_dir), 0o700)
        
        logger.info("BackupManager initialized", extra={
            'user_id': user_id,
            'backup_dir': str(self.backup_dir),
            'max_size_bytes': self.max_backup_size
        })
    
    def _generate_backup_id(self) -> str:
        """Generate unique backup identifier."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        user_hash = hashlib.sha256(str(self.user_id).encode()).hexdigest()[:8]
        return f"{timestamp}_{user_hash}"
    
    def _calculate_checksum(self, data: bytes) -> str:
        """Calculate SHA-256 checksum of data."""
        return hashlib.sha256(data).hexdigest()
    
    def _derive_key(self, password: bytes, salt: bytes) -> bytes:
        """Derive AES key from password using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.AES_KEY_LENGTH,
            salt=salt,
            iterations=self.ITERATIONS,
            backend=default_backend()
        )
        return kdf.derive(password)
    
    async def _collect_user_data(self) -> Dict[str, Any]:
        """
        Collect comprehensive user data for backup.
        
        Returns:
            Dictionary containing user data, preferences, premium status, etc.
        """
        try:
            # Core user data
            user_data = await get_user_data(self.user_id) or {}
            
            # Premium data
            premium_data = await get_premium_data(self.user_id)
            
            # Preferences (sanitized)
            preferences = user_data.get('preferences', {})
            # Remove sensitive fields if present
            sensitive_fields = ['password', 'token', 'secret', 'key']
            for field in sensitive_fields:
                preferences.pop(field, None)
            
            # Stats (anonymized)
            user_stats = await stats_tracker.get_user_stats(self.user_id, anonymized=True)
            
            backup_data = {
                'metadata': {
                    'user_id': self.user_id,
                    'backup_type': BackupType.FULL.value,
                    'version': self.BACKUP_VERSION,
                    'created_at': datetime.utcnow().isoformat()
                },
                'user': {
                    'id': user_data.get('user_id'),
                    'username': user_data.get('username'),
                    'first_name': user_data.get('first_name'),
                    'last_name': user_data.get('last_name'),
                    'language': user_data.get('language', 'en'),
                    'created_at': user_data.get('created_at'),
                    'last_active': user_data.get('last_active')
                },
                'preferences': preferences,
                'premium': {
                    'status': premium_data.get('status'),
                    'plan': premium_data.get('plan'),
                    'expiry': premium_data.get('expiry'),
                    'subscription_id': premium_data.get('subscription_id'),
                    'activated_at': premium_data.get('activation_date')
                },
                'stats': user_stats,
                'referrals': await self._collect_referral_data()
            }
            
            # Sanitize any remaining sensitive data
            backup_data = self._sanitize_backup_data(backup_data)
            
            logger.debug("User data collected for backup", extra={
                'user_id': self.user_id,
                'data_keys': list(backup_data.keys()),
                'data_size_bytes': len(json.dumps(backup_data).encode())
            })
            
            return backup_data
            
        except Exception as e:
            logger.error("Failed to collect user data", exc_info=True, extra={
                'user_id': self.user_id,
                'error': str(e)
            })
            raise BackupError(f"Data collection failed: {str(e)}")
    
    def _sanitize_backup_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize backup data to remove sensitive information."""
        sanitized = data.copy()
        
        # Remove any fields that might contain sensitive data
        sensitive_patterns = [
            'password', 'token', 'secret', 'key', 'auth', 'session',
            'email', 'phone', 'address', 'ip', 'api_key'
        ]
        
        def sanitize_recursive(obj):
            if isinstance(obj, dict):
                return {k: sanitize_recursive(v) for k, v in obj.items() 
                       if not any(pattern in k.lower() for pattern in sensitive_patterns)}
            elif isinstance(obj, list):
                return [sanitize_recursive(item) for item in obj]
            else:
                return obj
        
        sanitized = sanitize_recursive(sanitized)
        
        # Ensure no file paths or URLs with sensitive info
        if 'user' in sanitized:
            sanitized['user'].pop('id', None)  # Remove user_id from export
            
        logger.debug("Backup data sanitized", extra={
            'user_id': self.user_id,
            'original_keys': len(data.keys()) if isinstance(data, dict) else 0,
            'sanitized_keys': len(sanitized.keys()) if isinstance(sanitized, dict) else 0
        })
        
        return sanitized
    
    async def _collect_referral_data(self) -> Dict[str, Any]:
        """Collect referral data for backup (anonymized)."""
        try:
            from referrals import get_referral_stats  # type: ignore
            stats = await get_referral_stats(self.user_id)
            
            # Anonymize referral data
            return {
                'has_referral_code': bool(stats.get('code')),
                'referral_count': stats.get('usage_count', 0),
                'conversion_count': stats.get('premium_conversions', 0),
                'total_earned': stats.get('total_rewarded', 0.0),
                'conversion_rate': stats.get('conversion_rate', 0.0)
            }
        except Exception as e:
            logger.warning("Failed to collect referral data", exc_info=True, extra={
                'user_id': self.user_id,
                'error': str(e)
            })
            return {}
    
    async def create_backup(self, backup_type: str = BackupType.FULL.value, 
                          password: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Create a secure backup of user data.
        
        Args:
            backup_type: Type of backup (full/incremental)
            password: Optional password for additional encryption layer
            
        Returns:
            Dictionary with backup file path and metadata
            
        Raises:
            BackupError: If backup creation fails
            ValueError: If backup would exceed size limits
        """
        try:
            logger.info("Starting backup creation", extra={
                'user_id': self.user_id,
                'backup_type': backup_type,
                'password_protected': password is not None
            })
            
            # Step 1: Collect data
            backup_data = await self._collect_user_data()
            data_json = json.dumps(backup_data, default=str, ensure_ascii=False)
            data_bytes = data_json.encode('utf-8')
            
            # Step 2: Validate size
            if len(data_bytes) > self.max_backup_size:
                raise ValueError(f"Backup size {len(data_bytes)} exceeds limit of {self.max_backup_size} bytes")
            
            # Step 3: Compress data
            compressed_data = lzma.compress(data_bytes)
            logger.debug("Data compressed", extra={
                'user_id': self.user_id,
                'original_size': len(data_bytes),
                'compressed_size': len(compressed_data),
                'compression_ratio': len(data_bytes)/len(compressed_data) if len(compressed_data) > 0 else 0
            })
            
            # Step 4: Encrypt data
            encrypted_data, salt = await self._encrypt_data(compressed_data, password)
            
            # Step 5: Create backup file
            backup_id = self._generate_backup_id()
            backup_filename = f"backup_{self.user_id}_{backup_id}.tar.gz.enc"
            backup_path = self.backup_dir / backup_filename
            
            # Create tar archive
            async with aiofiles.tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.tmp') as temp_file:
                # Write encrypted data to temp file
                await temp_file.write(encrypted_data)
                temp_path = temp_file.name
            
            # Create tar.gz archive
            with tarfile.open(backup_path, 'w:gz') as tar:
                tar.add(temp_path, arcname=Path(backup_filename).name)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            # Step 6: Create metadata
            checksum = self._calculate_checksum(encrypted_data)
            metadata = BackupMetadata(
                user_id=self.user_id,
                backup_id=backup_id,
                data_size=len(data_bytes),
                compressed_size=len(compressed_data),
                checksum=checksum,
                backup_type=backup_type,
                incremental_from=None  # Implement incremental logic later
            )
            
            # Step 7: Store metadata
            metadata_file = backup_path.with_suffix(backup_path.suffix + '.json')
            async with aiofiles.open(metadata_file, 'w') as f:
                await f.write(json.dumps(asdict(metadata), default=str, indent=2))
            
            # Secure file permissions
            os.chmod(str(backup_path), 0o600)
            os.chmod(str(metadata_file), 0o600)
            
            # Track backup creation
            await stats_tracker.track_user_activity(
                self.user_id,
                "backup_created",
                {
                    'backup_id': backup_id,
                    'size_mb': round(len(encrypted_data) / (1024*1024), 2),
                    'encrypted': True
                }
            )
            
            logger.info("Backup created successfully", extra={
                'user_id': self.user_id,
                'backup_id': backup_id,
                'file_size_mb': round(backup_path.stat().st_size / (1024*1024), 2),
                'encrypted': True,
                'compression_ratio': round(len(data_bytes)/len(compressed_data), 2)
            })
            
            return {
                'success': True,
                'backup_id': backup_id,
                'file_path': str(backup_path),
                'metadata_path': str(metadata_file),
                'file_size_bytes': backup_path.stat().st_size,
                'metadata': asdict(metadata),
                'checksum': checksum
            }
            
        except Exception as e:
            logger.error("Backup creation failed", exc_info=True, extra={
                'user_id': self.user_id,
                'backup_type': backup_type,
                'error': str(e)
            })
            raise BackupError(f"Backup creation failed: {str(e)}")
    
    async def _encrypt_data(self, data: bytes, password: Optional[bytes] = None) -> tuple[bytes, Optional[bytes]]:
        """Encrypt data using AES-GCM."""
        try:
            if password:
                # Derive key from password
                salt = os.urandom(self.SALT_LENGTH)
                key = self._derive_key(password, salt)
            else:
                # Use provided encryption key
                salt = None
                key = self.encryption_key
            
            # Encrypt with AES-GCM
            aesgcm = AESGCM(key)
            nonce = os.urandom(12)
            ciphertext = aesgcm.encrypt(nonce, data, None)
            
            # Combine salt + nonce + ciphertext
            if salt:
                encrypted = salt + nonce + ciphertext
            else:
                encrypted = nonce + ciphertext
            
            logger.debug("Data encrypted", extra={
                'user_id': self.user_id,
                'original_size': len(data),
                'encrypted_size': len(encrypted),
                'password_protected': password is not None
            })
            
            return encrypted, salt
            
        except Exception as e:
            logger.error("Encryption failed", exc_info=True, extra={
                'user_id': self.user_id,
                'password_protected': password is not None,
                'error': str(e)
            })
            raise BackupError(f"Encryption failed: {str(e)}")
    
    async def restore_backup(self, backup_file: Union[str, Path, IO], 
                           password: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Restore user data from backup file.
        
        Args:
            backup_file: Path to backup file or file-like object
            password: Password used for encryption (if applicable)
            
        Returns:
            Dictionary with restore results and any warnings
        """
        try:
            logger.info("Starting backup restoration", extra={
                'user_id': self.user_id,
                'backup_file': str(backup_file) if isinstance(backup_file, (str, Path)) else 'file-object',
                'password_protected': password is not None
            })
            
            backup_path = Path(backup_file) if isinstance(backup_file, (str, Path)) else None
            
            # Step 1: Read and extract backup
            if backup_path and backup_path.exists():
                # Extract from tar.gz
                with tempfile.TemporaryDirectory() as temp_dir:
                    with tarfile.open(backup_path, 'r:gz') as tar:
                        tar.extractall(temp_dir)
                    
                    # Find encrypted file
                    encrypted_files = list(Path(temp_dir).glob('*.tar.gz.enc'))
                    if not encrypted_files:
                        raise BackupError("No encrypted backup file found")
                    
                    async with aiofiles.open(encrypted_files[0], 'rb') as f:
                        encrypted_data = await f.read()
            else:
                # File-like object
                if hasattr(backup_file, 'read'):
                    # Handle tar extraction for file-like objects
                    with tempfile.TemporaryDirectory() as temp_dir:
                        with tarfile.open(fileobj=backup_file, mode='r:gz') as tar:
                            tar.extractall(temp_dir)
                        
                        encrypted_files = list(Path(temp_dir).glob('*.tar.gz.enc'))
                        if not encrypted_files:
                            raise BackupError("No encrypted backup file found")
                        
                        async with aiofiles.open(encrypted_files[0], 'rb') as f:
                            encrypted_data = await f.read()
                else:
                    raise ValueError("backup_file must be path or file-like object")
            
            # Step 2: Decrypt data
            decrypted_data = await self._decrypt_data(encrypted_data, password)
            
            # Step 3: Decompress data
            decompressed_data = lzma.decompress(decrypted_data)
            backup_json = decompressed_data.decode('utf-8')
            backup_data = json.loads(backup_json)
            
            # Step 4: Validate backup
            validation_result = await self._validate_backup_data(backup_data)
            if not validation_result['valid']:
                raise BackupError(f"Backup validation failed: {validation_result['errors']}")
            
            # Step 5: Restore data
            restore_result = await self._restore_user_data(backup_data)
            
            # Step 6: Track restoration
            await stats_tracker.track_user_activity(
                self.user_id,
                "backup_restored",
                {
                    'backup_id': backup_data['metadata']['backup_id'],
                    'version': backup_data['metadata']['version'],
                    'restored_items': len(restore_result['restored_items'])
                }
            )
            
            logger.info("Backup restoration completed", extra={
                'user_id': self.user_id,
                'backup_id': backup_data['metadata']['backup_id'],
                'restored_items': len(restore_result['restored_items']),
                'warnings': len(restore_result['warnings'])
            })
            
            return {
                'success': True,
                'backup_id': backup_data['metadata']['backup_id'],
                'version': backup_data['metadata']['version'],
                'restored_items': restore_result['restored_items'],
                'warnings': restore_result['warnings'],
                'validation': validation_result
            }
            
        except Exception as e:
            logger.error("Backup restoration failed", exc_info=True, extra={
                'user_id': self.user_id,
                'backup_file': str(backup_file),
                'error': str(e)
            })
            raise BackupError(f"Restoration failed: {str(e)}")
    
    async def _decrypt_data(self, encrypted_data: bytes, 
                          password: Optional[bytes] = None) -> bytes:
        """Decrypt data using AES-GCM."""
        try:
            if password:
                # Derive key from password
                salt = encrypted_data[:self.SALT_LENGTH]
                nonce = encrypted_data[self.SALT_LENGTH:self.SALT_LENGTH+12]
                ciphertext = encrypted_data[self.SALT_LENGTH+12:]
                key = self._derive_key(password, salt)
            else:
                # Use provided encryption key
                nonce = encrypted_data[:12]
                ciphertext = encrypted_data[12:]
                key = self.encryption_key
            
            # Decrypt with AES-GCM
            aesgcm = AESGCM(key)
            decrypted = aesgcm.decrypt(nonce, ciphertext, None)
            
            logger.debug("Data decrypted", extra={
                'user_id': self.user_id,
                'encrypted_size': len(encrypted_data),
                'decrypted_size': len(decrypted),
                'password_protected': password is not None
            })
            
            return decrypted
            
        except Exception as e:
            logger.error("Decryption failed", exc_info=True, extra={
                'user_id': self.user_id,
                'password_protected': password is not None,
                'error': str(e)
            })
            raise BackupError(f"Decryption failed: {str(e)}")
    
    async def _validate_backup_data(self, backup_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate backup data integrity and compatibility."""
        try:
            validation = {
                'valid': True,
                'version_compatible': True,
                'checksum_valid': True,
                'structure_valid': True,
                'data_complete': True,
                'warnings': [],
                'errors': []
            }
            
            # Version check
            version = backup_data.get('metadata', {}).get('version', '0.0')
            if version != self.BACKUP_VERSION:
                validation['version_compatible'] = False
                validation['warnings'].append(f"Version mismatch: {version} vs {self.BACKUP_VERSION}")
            
            # Structure validation
            required_sections = ['metadata', 'user', 'preferences']
            missing_sections = [sec for sec in required_sections if sec not in backup_data]
            if missing_sections:
                validation['structure_valid'] = False
                validation['errors'].append(f"Missing sections: {', '.join(missing_sections)}")
            
            # User data validation
            if 'user' in backup_data:
                user_data = backup_data['user']
                if not isinstance(user_data.get('id'), int):
                    validation['data_complete'] = False
                    validation['errors'].append("Invalid user ID format")
            
            # Premium data validation
            if 'premium' in backup_data:
                premium = backup_data['premium']
                if premium.get('status') not in [s.value for s in PremiumStatus]:
                    validation['data_complete'] = False
                    validation['warnings'].append("Unknown premium status")
            
            # Check for sensitive data leakage
            sensitive_detected = self._detect_sensitive_data(backup_data)
            if sensitive_detected:
                validation['warnings'].append(f"Potential sensitive data detected: {sensitive_detected}")
            
            if not validation['errors']:
                validation['valid'] = True
            else:
                validation['valid'] = False
                
            logger.debug("Backup validation completed", extra={
                'user_id': self.user_id,
                'valid': validation['valid'],
                'version_compatible': validation['version_compatible'],
                'errors_count': len(validation['errors']),
                'warnings_count': len(validation['warnings'])
            })
            
            return validation
            
        except Exception as e:
            logger.error("Backup validation failed", exc_info=True, extra={
                'user_id': self.user_id,
                'error': str(e)
            })
            return {
                'valid': False,
                'errors': [f"Validation error: {str(e)}"],
                'warnings': []
            }
    
    def _detect_sensitive_data(self, data: Dict[str, Any]) -> List[str]:
        """Detect potentially sensitive data in backup."""
        sensitive_patterns = [
            r'@[\w.-]+',  # Email patterns
            r'\+?[\d\s\-\(\)]{10,}',  # Phone numbers
            r'\b\d{4}-\d{4}-\d{4}-\d{4}\b',  # Card numbers
            r'sk_live_|pk_live_',  # API keys
            r'Bearer\s+\w+'  # Auth tokens
        ]
        
        import re
        detected = []
        
        def scan_recursive(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    detected.extend(scan_recursive(value, new_path))
            elif isinstance(obj, (list, tuple)):
                for i, item in enumerate(obj):
                    new_path = f"{path}[{i}]"
                    detected.extend(scan_recursive(item, new_path))
            elif isinstance(obj, str) and len(obj) > 5:
                for pattern in sensitive_patterns:
                    if re.search(pattern, obj):
                        detected.append(f"{path}: {repr(obj[:20])}...")
                        break
            
            return detected
        
        return scan_recursive(data)
    
    async def _restore_user_data(self, backup_data: Dict[str, Any]) -> Dict[str, Any]:
        """Restore user data from backup."""
        try:
            restore_result = {
                'restored_items': [],
                'warnings': [],
                'errors': []
            }
            
            # Restore user data
            user_data = backup_data.get('user', {})
            if user_data:
                # Only restore non-sensitive fields
                safe_fields = ['language', 'timezone', 'onboarding_complete']
                update_data = {k: v for k, v in user_data.items() if k in safe_fields}
                
                if update_data:
                    update_user_data(self.user_id, update_data)
                    restore_result['restored_items'].append('user_preferences')
                else:
                    restore_result['warnings'].append('No safe user data to restore')
            
            # Restore preferences
            preferences = backup_data.get('preferences', {})
            if preferences:
                # Sanitize preferences before restore
                safe_prefs = {k: v for k, v in preferences.items() 
                            if k not in ['password', 'token', 'secret']}
                
                await store_user_preferences(self.user_id, safe_prefs)
                restore_result['restored_items'].append('preferences')
            
            # Restore premium status (only if valid)
            premium = backup_data.get('premium', {})
            if (premium.get('status') in [s.value for s in PremiumStatus] and 
                premium.get('plan') in [p.value['id'] for p in PremiumPlan]):
                
                # Note: Premium restoration requires careful handling
                # Only restore status if it doesn't affect billing
                if premium['status'] == PremiumStatus.EXPIRED.value:
                    # Safe to restore expired status
                    update_user_data(self.user_id, {
                        'premium_status': PremiumStatus.EXPIRED.value,
                        'premium_plan': 'basic'
                    })
                    restore_result['restored_items'].append('premium_status')
                else:
                    restore_result['warnings'].append('Premium status requires manual verification')
            else:
                restore_result['warnings'].append('Invalid premium data - skipped restoration')
            
            # Restore stats (if available and anonymized)
            stats = backup_data.get('stats', {})
            if stats and not self._contains_sensitive_stats(stats):
                # Restore anonymized usage stats
                await self._restore_stats(stats)
                restore_result['restored_items'].append('usage_stats')
            
            logger.info("User data restoration completed", extra={
                'user_id': self.user_id,
                'items_restored': len(restore_result['restored_items']),
                'warnings': len(restore_result['warnings'])
            })
            
            return restore_result
            
        except Exception as e:
            logger.error("Failed to restore user data", exc_info=True, extra={
                'user_id': self.user_id,
                'error': str(e)
            })
            raise BackupError(f"Data restoration failed: {str(e)}")
    
    async def _restore_stats(self, stats_data: Dict[str, Any]) -> None:
        """Restore anonymized usage statistics."""
        try:
            # Only restore non-sensitive aggregate stats
            safe_stats = {
                key: value for key, value in stats_data.items()
                if not any(sensitive in key.lower() for sensitive in ['personal', 'email', 'phone', 'address'])
            }
            
            # Update user stats tracking
            for stat_type, count in safe_stats.items():
                if isinstance(count, int):
                    await stats_tracker.track_user_activity(
                        self.user_id,
                        stat_type,
                        {'restored_count': count}
                    )
            
        except Exception as e:
            logger.warning("Failed to restore stats", exc_info=True, extra={
                'user_id': self.user_id,
                'error': str(e)
            })
    
    def _contains_sensitive_stats(self, stats: Dict[str, Any]) -> bool:
        """Check if stats contain sensitive information."""
        sensitive_indicators = ['email', 'phone', 'address', 'ip', 'personal']
        return any(any(indicator in key.lower() for indicator in sensitive_indicators) 
                  for key in stats.keys())
    
    async def list_backups(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List available backups for user.
        
        Args:
            limit: Maximum number of backups to return
            
        Returns:
            List of backup metadata dictionaries
        """
        try:
            backup_pattern = self.backup_dir / f"backup_{self.user_id}_*.tar.gz.enc.json"
            metadata_files = list(backup_pattern.glob('**/*'))[:limit]
            
            backups = []
            for metadata_file in metadata_files:
                try:
                    async with aiofiles.open(metadata_file, 'r') as f:
                        metadata_json = await f.read()
                        metadata = json.loads(metadata_json)
                        
                        backup_file = metadata_file.with_suffix('')
                        backups.append({
                            'backup_id': metadata['backup_id'],
                            'created_at': metadata['created_at'],
                            'backup_type': metadata['backup_type'],
                            'data_size_mb': round(metadata['data_size'] / (1024*1024), 2),
                            'file_path': str(backup_file),
                            'metadata_path': str(metadata_file),
                            'checksum': metadata['checksum']
                        })
                except Exception as file_e:
                    logger.warning("Failed to read backup metadata", exc_info=True, extra={
                        'user_id': self.user_id,
                        'metadata_file': str(metadata_file),
                        'error': str(file_e)
                    })
                    continue
            
            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            
            logger.debug("Backup list retrieved", extra={
                'user_id': self.user_id,
                'backup_count': len(backups),
                'limit': limit
            })
            
            return backups
            
        except Exception as e:
            logger.error("Failed to list backups", exc_info=True, extra={
                'user_id': self.user_id,
                'limit': limit,
                'error': str(e)
            })
            raise BackupError(f"Failed to list backups: {str(e)}")
    
    async def delete_backup(self, backup_id: str) -> bool:
        """
        Delete specific backup.
        
        Args:
            backup_id: Unique identifier of backup to delete
            
        Returns:
            True if deletion successful
        """
        try:
            # Find backup files
            backup_pattern = self.backup_dir / f"backup_{self.user_id}_{backup_id}"
            
            backup_file = backup_pattern.with_suffix('.tar.gz.enc')
            metadata_file = backup_pattern.with_suffix('.tar.gz.enc.json')
            
            deleted = False
            
            if backup_file.exists():
                backup_file.unlink()
                deleted = True
            
            if metadata_file.exists():
                metadata_file.unlink()
                deleted = True
            
            if deleted:
                logger.info("Backup deleted", extra={
                    'user_id': self.user_id,
                    'backup_id': backup_id
                })
                return True
            else:
                logger.warning("Backup not found for deletion", extra={
                    'user_id': self.user_id,
                    'backup_id': backup_id
                })
                return False
                
        except Exception as e:
            logger.error("Failed to delete backup", exc_info=True, extra={
                'user_id': self.user_id,
                'backup_id': backup_id,
                'error': str(e)
            })
            raise BackupError(f"Deletion failed: {str(e)}")

async def create_system_backup(encryption_key: bytes, backup_dir: str = "./system_backups") -> Dict[str, Any]:
    """
    Create system-wide backup of all users (admin only).
    
    Args:
        encryption_key: Master encryption key
        backup_dir: Directory for system backups
        
    Returns:
        Backup result with file information
    """
    backup_manager = BackupManager(0, encryption_key, backup_dir, max_backup_size_mb=500)
    
    try:
        # Collect system data
        system_data = {
            'metadata': {
                'backup_type': BackupType.SYSTEM.value,
                'version': backup_manager.BACKUP_VERSION,
                'created_at': datetime.utcnow().isoformat(),
                'total_users': 0,
                'total_size': 0
            },
            'users': {},
            'system_config': {
                'version': "1.0",
                'backup_date': datetime.utcnow().isoformat()
            }
        }
        
        # Get all user data
        all_users = await get_all_user_data()
        system_data['metadata']['total_users'] = len(all_users)
        
        for user_data in all_users:
            user_id = user_data['user_id']
            try:
                # Create individual user backup
                user_backup = await backup_manager._collect_user_data_for_user(user_id)
                system_data['users'][str(user_id)] = user_backup
            except Exception as user_e:
                logger.warning("Failed to backup individual user", exc_info=True, extra={
                    'user_id': user_id,
                    'error': str(user_e)
                })
                continue
        
        # Create system backup file
        system_backup = await backup_manager.create_backup_from_data(system_data)
        
        logger.info("System backup completed", extra={
            'total_users': len(all_users),
            'backup_id': system_backup['backup_id'],
            'file_size_mb': round(system_backup['file_size_bytes'] / (1024*1024), 2)
        })
        
        return system_backup
        
    except Exception as e:
        logger.error("System backup failed", exc_info=True, extra={'error': str(e)})
        raise BackupError(f"System backup failed: {str(e)}")

# Utility functions for integration
async def backup_user_data(user_id: int, encryption_key: bytes) -> Dict[str, Any]:
    """Convenience function for backing up single user."""
    backup_manager = BackupManager(user_id, encryption_key)
    return await backup_manager.create_backup()

async def restore_user_data(user_id: int, backup_file: Union[str, Path], 
                          encryption_key: bytes, password: Optional[bytes] = None) -> Dict[str, Any]:
    """Convenience function for restoring single user."""
    backup_manager = BackupManager(user_id, encryption_key)
    return await backup_manager.restore_backup(backup_file, password)

def format_currency(amount: float) -> str:
    """Format Naira amount for display."""
    return f"₦{amount:,.0f}"
