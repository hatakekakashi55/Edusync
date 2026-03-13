"""
EduSync Backend - Docker Code Executor
Handles code execution in isolated Docker containers.
"""
import logging
import os
import asyncio
import tempfile
import time
from datetime import datetime
from typing import Dict, Any

from app.config import LANG_CONFIG, DOCKER_CPU, DOCKER_MEMORY, TIMEOUT_SECONDS
from app.models.challenge import CodeExecution

logger = logging.getLogger("edusync")

# =============== DOCKER CODE EXECUTION FUNCTIONS ===============

async def execute_code_in_docker(execution_request: CodeExecution) -> Dict[str, Any]:
    """
    Execute code in Docker container
    Supports multiple languages: Python, JavaScript, Java, C, C++, Go, Rust
    """
    try:
        language = execution_request.language.lower()
        code = execution_request.code
        input_data = execution_request.input_data or ""
        
        # Validate language
        if language not in LANG_CONFIG:
            return {
                "success": False,
                "error": f"Unsupported language: {language}. Supported: {', '.join(LANG_CONFIG.keys())}",
                "output": "",
                "execution_time": 0
            }
        
        # Get language config
        lang_config = LANG_CONFIG[language]
        
        # Create temporary file with code
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{lang_config["file_ext"]}', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Prepare Docker command
            container_name = f"code-runner-{language}-{datetime.now().timestamp()}"
            
            # Mount the temp file
            docker_cmd = [
                "docker", "run",
                "--rm",
                f"--name={container_name}",
                f"--cpus={DOCKER_CPU}",
                f"--memory={DOCKER_MEMORY}",
                f"--timeout={TIMEOUT_SECONDS}",
                "-v", f"{temp_file}:/code/{os.path.basename(temp_file)}",
                "-w", "/code",
                lang_config["image"]
            ]
            
            # Add compile command if needed
            if lang_config.get("compile_cmd"):
                compile_cmd = lang_config["compile_cmd"].format(filename=os.path.basename(temp_file))
                docker_cmd.extend(["sh", "-c", f"{compile_cmd} && {lang_config['run_cmd'].format(filename=os.path.basename(temp_file))}"])
            else:
                run_cmd = lang_config["run_cmd"].format(filename=os.path.basename(temp_file))
                docker_cmd.extend(["sh", "-c", run_cmd])
            
            # Execute in Docker
            start_time = time.time()
            
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=input_data.encode() if input_data else b""),
                    timeout=TIMEOUT_SECONDS
                )
                
                execution_time = time.time() - start_time
                
                output = stdout.decode('utf-8', errors='replace') if stdout else ""
                error = stderr.decode('utf-8', errors='replace') if stderr else ""
                
                return {
                    "success": process.returncode == 0,
                    "output": output.strip(),
                    "error": error.strip() if error else None,
                    "execution_time": execution_time,
                    "return_code": process.returncode,
                    "language": language
                }
                
            except asyncio.TimeoutError:
                await process.kill()
                return {
                    "success": False,
                    "error": f"Execution timeout (exceeded {TIMEOUT_SECONDS} seconds)",
                    "output": "",
                    "execution_time": TIMEOUT_SECONDS,
                    "return_code": -1,
                    "language": language
                }
        
        finally:
            # Clean up temp file
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    except Exception as e:
        logger.error(f"Docker execution error: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Execution error: {str(e)}",
            "output": "",
            "execution_time": 0,
            "return_code": -1,
            "language": execution_request.language
        }


async def run_code():
    """
    Simple wrapper to run code from CodeExecution request
    For standalone code execution without HTTP request context
    """
    try:
        execution_request = CodeExecution(
            code="",
            language="python",
            input_data=""
        )
        
        result = await execute_code_in_docker(execution_request)
        return result
    
    except Exception as e:
        logger.error(f"Run code error: {e}")
        return {
            "success": False,
            "error": str(e),
            "output": "",
            "execution_time": 0
        }
