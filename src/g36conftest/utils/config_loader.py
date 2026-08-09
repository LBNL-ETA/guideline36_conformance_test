"""Configuration loading and merging utilities."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_config(
    project_root: Path,
    global_config_path: Optional[Path] = None,
    test_config_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Load and merge global and test-specific configurations.
    
    The global config determines which test to run and which device type to use.
    The test-specific config contains device settings and test parameters.
    
    Parameters
    ----------
    project_root : Path
        Path to project root directory
    global_config_path : Path, optional
        Path to global config file. Can be absolute or relative to project_root.
        If None, defaults to config/global_config.yaml
    test_config_path : Path, optional
        Path to test-specific config file. Can be absolute or relative to project_root.
        If None, uses test_type from global config to determine path:
        conformance_tests/{test_type}/config/config.yaml
        
    Returns
    -------
    config : dict
        Merged configuration dictionary with the following structure:
        {
            'test_type': str,
            'device_type': str,
            'device': dict,  # Device config for selected device_type
            'test': dict,
            'test_runner': dict,
            'logging': dict (optional)
        }
        
    Raises
    ------
    FileNotFoundError
        If config files are not found
    ValueError
        If required fields are missing or invalid
    """
    # Resolve global config path

    if global_config_path is None:
        global_config_path = project_root / "tests"/"config" / "global_config.yaml"
    elif not global_config_path.is_absolute():
        global_config_path = project_root / "tests"/ global_config_path
    if not global_config_path.exists():
        raise FileNotFoundError(
            f"Global config not found at {global_config_path}. "
            f"Copy config/global_config_template.yaml to config/global_config.yaml"
        )
    
    with open(global_config_path, 'r') as f:
        global_config = yaml.safe_load(f)
    
    # Validate global config
    if 'test_type' not in global_config:
        raise ValueError("Global config must specify 'test_type'")
    if 'device_type' not in global_config:
        raise ValueError("Global config must specify 'device_type'")
    
    test_type = global_config['test_type']
    device_type = global_config['device_type']
    
    # Resolve test-specific config path
    if test_config_path is None:
        test_config_path = project_root / "tests"/ "conformance_tests" / test_type / "config" / "config.yaml"
    elif not test_config_path.is_absolute():
        test_config_path = project_root / "tests"/ test_config_path
    if not test_config_path.exists():
        raise FileNotFoundError(
            f"Test config not found at {test_config_path}. "
            f"Copy conformance_tests/{test_type}/config/config_template.yaml to config.yaml"
        )
    
    with open(test_config_path, 'r') as f:
        test_config = yaml.safe_load(f)
    
    # Validate test config structure
    if 'device' not in test_config:
        raise ValueError(f"Test config must have 'device' section")
    if device_type not in test_config['device']:
        raise ValueError(
            f"Test config does not have configuration for device type '{device_type}'. "
            f"Available device types: {list(test_config['device'].keys())}"
        )
    if 'test' not in test_config:
        raise ValueError(f"Test config must have 'test' section")
    
    # Extract device config for selected device type
    device_config = test_config['device'][device_type].copy()
    device_config['type'] = device_type  # Add type field for backward compatibility
    
    # Build merged config
    merged_config = {
        'test_type': test_type,
        'device_type': device_type,
        'device': device_config,
        'test': test_config['test'],
        'test_runner': global_config.get('test_runner', {}),
    }
    
    # Add optional logging config if present
    if 'logging' in global_config:
        merged_config['logging'] = global_config['logging']
    
    return merged_config
