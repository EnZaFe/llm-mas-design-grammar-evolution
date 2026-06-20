import json
import random
import os
import copy
import csv
import textwrap
from langchain_openai import ChatOpenAI
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
from agent_variants import AGENT_VARIANTS, AGENT_MODELS_veryheavy, AGENT_MODELS_node03, AGENT_MODELS_node150, AGENT_MODELS_API
# Silence noisy fixed-agent initialization prints when True
QUIET_FIXED_AGENT_LOGS = True
# Silence compiler initialization prints when True
QUIET_COMPILER_LOGS = True

def gen_init():
    return textwrap.dedent("""
        # Imports
        import os
        import subprocess
        from tempfile import NamedTemporaryFile
        from pydantic import BaseModel, Field
        from crewai import Agent, Crew, Process, Task, LLM
        from crewai.project import CrewBase, agent, crew, task
        from crewai.flow.flow import Flow, listen, router, start, or_
        from langchain_openai import ChatOpenAI
        from local_llm_provider import LocalLLM
        import logging
        from datetime import datetime
        import sys
        import re
        import time
        from contextlib import contextmanager
        import signal
        import json
        from pathlib import Path
        from openai import OpenAI

        # Global toggle for non-essential initialization logs
        QUIET_COMPILER_LOGS = True
         
        client = OpenAI()
        IS_WINDOWS = os.name == "nt"

        class ResponsesLLM:
            def __init__(self, model_name: str):
                self.model_name = model_name

            def __call__(self, prompt: str) -> str:
                resp = client.responses.create(
                    model=self.model_name,
                    input=prompt,
                )
                return resp.output_text
                           
        @contextmanager
        def global_timeout(seconds):
            if IS_WINDOWS:
                yield
                return

            def handler(signum, frame):
                raise TimeoutError(f"Global execution timeout ({seconds}s) exceeded")
            old_handler = signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)
            try:
                yield
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
                           
        def setup_logger(ind_id, problem_id, output_dir):
            os.makedirs(output_dir, exist_ok=True)


            logger_name = f"DiagramFlow.{ind_id}.{problem_id}"
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.DEBUG)

            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            
            log_filename = os.path.join(output_dir, f"problem_{problem_id}.log")
            

            if logger.handlers:
                return logger, log_filename

            fh = logging.FileHandler(log_filename, encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(formatter)


            logger.addHandler(fh)

            return logger, log_filename
              
        def kickoff(ind_id, problem_id, problem_str="", output_folder=None):
            flow = Individual(ind_id, problem_id, problem_str, output_folder)
            flow.ind_id = ind_id
            flow.problem_id = problem_id
            flow.problem = problem_str
            flow.output_folder = output_folder

            try:
                with global_timeout(1000):  # Timeout general de 2 minutos por individuo
                    return flow.run_flow()
            except TimeoutError:
                print(f"❌ Timeout: Individual {ind_id} exceeded 1000s")
                return "__'TIMEOUT_PLACEHOLDER__"

        class Individual():
            def __init__(self, ind_id, problem_id, problem_str, output_folder):
                if output_folder is None:
                        raise ValueError("output_folder must be provided for logging")
                global LOGGER
                LOGGER, log_file = setup_logger(ind_id, problem_id, output_folder)
                LOGGER.info("="*70)
                LOGGER.info("WORKFLOW INITIALIZATION")
                LOGGER.info("="*70)
                LOGGER.info(f"Output directory: {output_folder}")
                LOGGER.info(f"Log file: {log_file}")
                LOGGER.info(f"Individual ID: {ind_id}")
                LOGGER.info(f"Problem ID: {problem_id}")
                LOGGER.info(f"Problem: {problem_str[:100]}..." if len(problem_str) > 100 else f"Problem: {problem_str}")
                
                LOGGER.info("Workflow initialized successfully")
                LOGGER.info("="*70)

                # State variables
                self.max_steps: int = 100 # Can be changed
                self.steps: int = 0 # At start
                           
                self.state = {
                    "analysis": "__'PLACEHOLDER_ANALYSIS__",
                    "architecture": "__'PLACEHOLDER_ARCHITECTURE__",
                    "code": "__'PLACEHOLDER_CODE__",
                    "syntax_valid": False,
                    "execution_valid": False,
                    "error": None,
                    "feedback": "__'PLACEHOLDER_FEEDBACK__",
                    "version": 0
                }
                           
                self.candidate_code: str = "__'PLACEHOLDER_CODE__"
                            
                self.llm: str = ""
    
                            
                self.ind_id = ind_id
                self.problem_id = problem_id
                self.problem = problem_str
                self.output_folder = output_folder


            def save_code_history(self):
                history_file = Path(self.output_folder) / f"code_history_{self.problem_id}.json"

                entry = {
                    "version": self.state["version"],
                    "analysis": self.state.get("analysis"),
                    "architecture": self.state.get("architecture"),
                    "code": self.state.get("code"),
                    "syntax_valid": self.state.get("syntax_valid"),
                    "execution_valid": self.state.get("execution_valid"),
                    "error": self.state.get("error"),
                    "feedback": self.state.get("feedback"),
                    "timestamp": datetime.now().isoformat(),
                }

                if history_file.exists():
                    with history_file.open("r", encoding="utf-8") as f:
                        history = json.load(f)
                else:
                    history = []

                # 🔑 REEMPLAZAR si la versión ya existe
                replaced = False
                for i, h in enumerate(history):
                    if h.get("version") == entry["version"]:
                        history[i] = entry
                        replaced = True
                        break

                # ➕ Añadir solo si es una versión nueva
                if not replaced:
                    history.append(entry)

                with history_file.open("w", encoding="utf-8") as f:
                    json.dump(history, f, indent=2)

                LOGGER.info(
                    f"Code history saved (v{entry['version']}, "
                    f"{'updated' if replaced else 'new'})"
                )
        """).strip()


def gen_agent(self, children, llm_type='LOCAL', model_family=None, gpu='node150'):
    role= ""
    goal= ""
    backstory= ""
    task = f"""
        Generate Python code to solve:
        {{self.problem}}

        Do not include any explanations or comments.
        Print the final result.
    """
    
    #children = type
    if len(children) == 0:
        agent_type = "UNDEFINED"
    else: # Lo que deberia hacer siempre
        agent_type = children[0]['value']
    if not QUIET_FIXED_AGENT_LOGS:
        print(f"{agent_type} , {gpu}, {model_family}")
    if model_family == None:
        family_models = None
        if not QUIET_FIXED_AGENT_LOGS:
            print('WARNING NO MODEL FAMILY SELECTED: habria que gestionar este error')

    #Provisional
    tool = ""
    output = "output"
    field_description = "field_description_placeholder"

    def get_fixed_config(agent_type, model_family, gpu):
        if not QUIET_FIXED_AGENT_LOGS:
            print(f'FIXED AGENT CONF: {agent_type}, {model_family}, {gpu}')
        if agent_type == "UNDEFINED":
            agent_type = random.choice(list(AGENT_VARIANTS.keys()))
        
        agent_general_type = agent_type.split("_")[0]
        fixed = AGENT_VARIANTS.get(agent_type, {})
        role = fixed.get("role", "Generic Agent")
        goal = fixed.get("goal", "Perform the assigned task")
        backstory = fixed.get("backstory", "No backstory provided")
        task = fixed.get("task", "Perform the assigned task")
        family_models=None
        if gpu == 'veryheavy':
            family_models= AGENT_MODELS_veryheavy.get(model_family, {})
        elif gpu == 'node150':
            family_models= AGENT_MODELS_node150.get(model_family, {})
        elif gpu in ('node03', 'node01', 'node02'):
            family_models= AGENT_MODELS_node03.get(model_family, {})
        elif gpu == 'API':
            family_models= AGENT_MODELS_API.get("openai", {})
            ################AÑADIR EL RESTO DE GPU
        print('Family Models selected:', family_models)
        llm_model = None
        if family_models is not None:
            llm_model = family_models.get(agent_general_type, None)
        
        if llm_model is None:
            raise ValueError(f"No model defined for agent_type {agent_type} in family {model_family}")

        return role, goal, backstory, task, llm_model
    if self.direct_llm is not None: # Llamada directa
        llm_agent = self.direct_llm 
    elif self.agent_config == 'Dynamic_LLM':
        messages = [
            (
                "system",
                "You are an expert agent prompt designer. "
                "Remember you are generating configuration for an agent in a workflow diagram."
                "The final purpose of the workflow is to generate a code that solves a input problem."
                "If the agent type is UNDEFINED, choose the best role to fulfill it's part of the workflow."
                f"Based on the agent type: {agent_type}, and workflow: {self.diagram}, "
                "generate a JSON object with fields: role, goal, backstory, task. "
                "Output valid JSON only, no markdown or explanations.",
            )
        ]
        llm = ChatOpenAI(
            model_name= 'openai-4-mini' ### HAY QUE GESTIONAR los llm de la API
        )
        response = llm.invoke(messages)
        print("[DynamicAgent] Raw AI output:", response.text)

        try:
            dynamic_config = json.loads(response.content)
            role = dynamic_config.get("role", "")
            goal = dynamic_config.get("goal", "")
            backstory = dynamic_config.get("backstory", "")
            task = dynamic_config.get("task", "")

        except (json.JSONDecodeError, ValueError):
            if not QUIET_FIXED_AGENT_LOGS:
                print(f"[DynamicAgent-{agent_type}] ❌ Dynamic generation failed. Falling back to fixed config.")
            role, goal, backstory, task = get_fixed_config(agent_type, model_family, gpu)
    else: #Fixed:
            if not QUIET_FIXED_AGENT_LOGS:
                print('Getting  fixed config..')
            role, goal, backstory, task, llm_agent = get_fixed_config(agent_type, model_family, gpu)
            if not QUIET_FIXED_AGENT_LOGS:
                print(f"[FixedAgent-{agent_type}] Using fixed configuration. role: {role}, llm_agent: {llm_agent}")
    
    if llm_type == 'LOCAL':
        try:
            model = (
                    'LocalLLM('
                    f'model="{llm_agent}", '
                    'temperature=0.0, '
                    'max_tokens=1024,'
                    'timeout_seconds=300'
                    ')'
                )
        except Exception as e:
            print(f"[LocalLLM-{agent_type}] ❌ Local LLM initialization failed. Model: {llm_agent}. Error: {str(e)}")
            print("[LocalLLM] Falling back to general local LLM.")
            model = (
                    'LocalLLM()'
                )
    else: #API
        model = f'ResponsesLLM(model_name="{llm_agent}")'

    if agent_type.startswith("CODER") or agent_type.startswith("FIXER") or (self.direct_llm is not None):
        save_var = f'''
            def extract_code(result: str) -> str:
                if not result or not result.strip():
                    return False, "__COULDN'T EXTRACT CODE PLACEHOLDER__"
                
                # Strategy 1: Try to find markdown code blocks (with or without language tag)
                code_fence_pattern = "```(?:\\w+)?\\s*\\n(.*?)```"
                matches = re.findall(code_fence_pattern, result, re.DOTALL)
                if matches:
                    return True, max(matches, key=len).strip()
                
                # Strategy 2: Look for Python-like code patterns
                lines = result.split('\\n')
                code_lines = []
                in_code_block = False
                
                # Indicators that a line is likely code
                code_indicators = [
                    "^\\s*def\\s+\\w+\\s*\\(",
                    "^\\s*class\\s+\\w+",
                    "^\\s*import\\s+",
                    "^\\s*from\\s+\\w+\\s+import",
                    "^\\s*@\\w+",
                    "^\\s*if\\s+__name__\\s*==",
                    "^\\s*return\\s+",
                    "^\\s*for\\s+\\w+\\s+in\\s+",
                    "^\\s*while\\s+",
                    "^\\s*try\\s*:",
                    "^\\s*except\\s*",
                    "^\\s*with\\s+",
                ]
                
                for line in lines:
                    is_code_line = any(re.match(pattern, line) for pattern in code_indicators)
                    
                    if code_lines and line.startswith((' ', '\\t')) and line.strip():
                        is_code_line = True
                    
                    if '=' in line and not line.strip().startswith('#'):
                        stripped = line.strip()
                        if not stripped.startswith(('http', 'https', '=')):
                            is_code_line = True
                    
                    if is_code_line:
                        in_code_block = True
                        code_lines.append(line)
                    elif in_code_block and not line.strip():
                        code_lines.append(line)
                    elif in_code_block and line.strip() and not line.strip().startswith('#'):
                        break
                
                if code_lines:
                    extracted = '\\n'.join(code_lines).strip()
                    if len(extracted) > 10 and not extracted.startswith('#'):
                        return True, extracted
                
                # Strategy 3: Try to find code between common markers
                patterns_to_try = [
                    "Here(?:'s| is) the code:?\\s*\\n(.*?)(?:\\n\\n|\\Z)",
                    "Solution:?\\s*\\n(.*?)(?:\\n\\n|\\Z)",
                    "Implementation:?\\s*\\n(.*?)(?:\\n\\n|\\Z)",
                ]
                
                for pattern in patterns_to_try:
                    match = re.search(pattern, result, re.DOTALL | re.IGNORECASE)
                    if match:
                        candidate = match.group(1).strip()
                        if any(keyword in candidate for keyword in ['def ', 'class ', 'import ', 'return ', 'for ', 'if ']):
                            return True, candidate
                
                # Strategy 4: If the entire response looks like code, use it
                if result.count('def ') + result.count('return ') + result.count('import ') > 0:
                    code_start = 0
                    code_end = len(lines)
                    
                    for i, line in enumerate(lines):
                        if any(re.match(pattern, line) for pattern in code_indicators):
                            code_start = i
                            break
                    
                    for i in range(len(lines) - 1, code_start, -1):
                        line = lines[i].strip()
                        if line and not line.startswith('#'):
                            code_end = i + 1
                            break
                    
                    if code_start < code_end:
                        extracted = '\\n'.join(lines[code_start:code_end]).strip()
                        if extracted:
                            return True, extracted
                
                return False, "__COULDN'T EXTRACT CODE PLACEHOLDER__"

            there_is_code, extracted_code = extract_code(result)
        
            LOGGER.debug(f"Candidate code snippet: \\n {{extracted_code}}")

            if there_is_code:
                self.state["code"] = extracted_code
                self.state["syntax_valid"] = False
                self.state["execution_valid"] = False
                self.state["error"] = None
                self.state["feedback"] = "New code candidate"
                self.state["version"] += 1

                LOGGER.debug(f"Code snippet: {{self.state['code']}}")
            else:
                LOGGER.warning("No valid python code block found in LLM output")
        '''.strip()
    elif agent_type.startswith("ANALYST"):
        save_var = '''
            def extract_answer(result: str) -> str:
                """
                Extrae el texto de la respuesta hasta encontrar marcadores de fin comunes
                en respuestas de modelos LLM. Usa patrones regex para mayor flexibilidad.
                Funciona incluso cuando hay texto antes o después de los marcadores.
                
                Args:
                    result: Texto completo de la respuesta del modelo
                    
                Returns:
                    Texto extraído hasta el primer marcador de fin encontrado, 
                    o el texto completo si no hay marcadores
                """
                # Patrones de marcadores de fin (de más específicos a más generales)
                # Usamos .*? para capturar texto antes y (?P<marker>...) para identificar el marcador
                end_patterns = [
                    # Marcadores explícitos de fin de respuesta
                    r'.*?(?P<marker>End of (Final )?Answer\\.?)',
                    r'.*?(?P<marker>\\[End of (Final )?Answer\\])',
                    r'.*?(?P<marker>\\*\\*End of (Final )?Answer\\*\\*)',
                    
                    # Marcadores de fin de pensamiento/análisis
                    r'.*?(?P<marker>End of (Thought|Analysis)( and Final Answer)?\\.?)',
                    r'.*?(?P<marker>\\[End of (Thought|Thinking|Analysis)\\])',
                    r'.*?(?P<marker>\\*\\*End of (Thought|Thinking|Analysis)( Process)?\\*\\*)',
                    
                    # Conclusiones formales
                    r'.*?(?P<marker>This concludes (our|the|my) .{0,50}?(analysis|response|answer))',
                    r'.*?(?P<marker>(In )?[Cc]onclusion:?)',
                    
                    # Agradecimientos y despedidas
                    r'.*?(?P<marker>Thank you for (considering|reading))',
                    r'.*?(?P<marker>Please let me know if (you|there))',
                    r'.*?(?P<marker>Feel free to (ask|reach out))',
                    r'.*?(?P<marker>If you (have|need) (any )?(questions|help))',
                    
                    # Frases meta-explicativas
                    r'.*?(?P<marker>The solution involves)',
                    r'.*?(?P<marker>This approach ensures)',
                    r'.*?(?P<marker>This method guarantees)',
                    r'.*?(?P<marker>The (above|following) (code|solution|approach))',
                    
                    # Marcadores técnicos
                    r'.*?(?P<marker>(Human resources?|HR) depart?ment)',
                    r'.*?(?P<marker>End!\\]\\}+)',
                    r'.*?(?P<marker>EOF)',
                    r'.*?(?P<marker>END OF (THE )?(PROJECT|CODE|SECTION))',
                    r'.*?(?P<marker>###\\s*END OF)',
                    
                    # Patrones genéricos de cierre
                    r'.*?(?P<marker>\\[END\\])',
                    r'.*?(?P<marker>---END---)',
                    r'.*?(?P<marker><<<END>>>)',
                ]
                
                # Buscar el primer patrón que aparezca en el texto
                earliest_position = len(result)
                found_pattern = None
                
                for pattern in end_patterns:
                    # Buscar con case-insensitive para mayor flexibilidad
                    match = re.search(pattern, result, re.IGNORECASE | re.MULTILINE)
                    if match:
                        # Obtener la posición donde empieza el marcador (no el texto antes)
                        marker_start = match.start('marker')
                        
                        if marker_start < earliest_position:
                            earliest_position = marker_start
                            found_pattern = pattern
                
                # Si se encontró algún marcador, extraer hasta ese punto
                if found_pattern and earliest_position < len(result):
                    LOGGER.info(f"End pattern founded, removing it... pattern: {found_pattern}")
                    extracted = result[:earliest_position].strip()
                    # Remover líneas vacías finales
                    extracted = re.sub(r'\\n\\s*\\n\\s*$', '', extracted)
                    return extracted
                
                # Si no se encontró ningún marcador, devolver el texto completo
                return result.strip()

            extracted_analysis = extract_answer(result)

            self.state["analysis"] = result
            LOGGER.info(f"Analysis updated for code version {self.state['version']}")
            LOGGER.debug(f"Analysis: {result}")
        '''.strip()
    elif agent_type.startswith("REVIEWER"): 
        save_var = '''
            def extract_answer(result: str) -> str:
                """
                Extrae el texto de la respuesta hasta encontrar marcadores de fin comunes
                en respuestas de modelos LLM. Usa patrones regex para mayor flexibilidad.
                Funciona incluso cuando hay texto antes o después de los marcadores.
                
                Args:
                    result: Texto completo de la respuesta del modelo
                    
                Returns:
                    Texto extraído hasta el primer marcador de fin encontrado, 
                    o el texto completo si no hay marcadores
                """
                # Patrones de marcadores de fin (de más específicos a más generales)
                # Usamos .*? para capturar texto antes y (?P<marker>...) para identificar el marcador
                end_patterns = [
                    # Marcadores explícitos de fin de respuesta
                    r'.*?(?P<marker>End of (Final )?Answer\\.?)',
                    r'.*?(?P<marker>\\[End of (Final )?Answer\\])',
                    r'.*?(?P<marker>\\*\\*End of (Final )?Answer\\*\\*)',
                    
                    # Marcadores de fin de pensamiento/análisis
                    r'.*?(?P<marker>End of (Thought|Analysis)( and Final Answer)?\\.?)',
                    r'.*?(?P<marker>\\[End of (Thought|Thinking|Analysis)\\])',
                    r'.*?(?P<marker>\\*\\*End of (Thought|Thinking|Analysis)( Process)?\\*\\*)',
                    
                    # Conclusiones formales
                    r'.*?(?P<marker>This concludes (our|the|my) .{0,50}?(analysis|response|answer))',
                    r'.*?(?P<marker>(In )?[Cc]onclusion:?)',
                    
                    # Agradecimientos y despedidas
                    r'.*?(?P<marker>Thank you for)',
                    r'.*?(?P<marker>Please let me know if )',
                    r'.*?(?P<marker>Feel free to)',
                    r'.*?(?P<marker>If you (have|need))',
                    
                    # Frases meta-explicativas
                    r'.*?(?P<marker>The solution involves)',
                    r'.*?(?P<marker>This approach ensures)',
                    r'.*?(?P<marker>This method guarantees)',
                    r'.*?(?P<marker>The (above|following) (code|solution|approach))',
                    
                    # Marcadores técnicos
                    r'.*?(?P<marker>(Human resources?|HR) depart?ment)',
                    r'.*?(?P<marker>End!\\]\\}+)',
                    r'.*?(?P<marker>EOF)',
                    r'.*?(?P<marker>END OF (THE )?(PROJECT|CODE|SECTION))',
                    r'.*?(?P<marker>###\\s*END OF)',
                    
                    # Patrones genéricos de cierre
                    r'.*?(?P<marker>\\[END\\])',
                    r'.*?(?P<marker>---END---)',
                    r'.*?(?P<marker><<<END>>>)',
                ]
                
                # Buscar el primer patrón que aparezca en el texto
                earliest_position = len(result)
                found_pattern = None
                
                for pattern in end_patterns:
                    # Buscar con case-insensitive para mayor flexibilidad
                    match = re.search(pattern, result, re.IGNORECASE | re.MULTILINE)
                    if match:
                        # Obtener la posición donde empieza el marcador (no el texto antes)
                        marker_start = match.start('marker')
                        
                        if marker_start < earliest_position:
                            earliest_position = marker_start
                            found_pattern = pattern
                
                # Si se encontró algún marcador, extraer hasta ese punto
                if found_pattern and earliest_position < len(result):
                    LOGGER.info(f"End pattern founded, removing it... pattern: {found_pattern}")
                    extracted = result[:earliest_position].strip()
                    # Remover líneas vacías finales
                    extracted = re.sub(r'\\n\\s*\\n\\s*$', '', extracted)
                    return extracted
                
                # Si no se encontró ningún marcador, devolver el texto completo
                return result.strip()

                
            extracted_analysis = extract_answer(result)

            self.state["feedback"] = result
            LOGGER.info(f"Message updated for code version {self.state['version']}")
            LOGGER.debug(f"Message: {result}")
        '''.strip()
    elif agent_type.startswith("ARCHITECT"): 
        save_var = f'''
            self.state["architecture"] = result
            LOGGER.info(f"Architecture updated for code version {{self.state['version']}}")
            LOGGER.debug(f"Architecture: {{result}}")
        '''.strip()
        
    else: #UNDEFINED
        save_var = "LOGGER.warning('UNDEFINED agent type - no state update')"
    # Real return
    return textwrap.dedent(f'''
        def node_{self.node}(self):
            LOGGER.info("="*70)
            LOGGER.info(f"ENTERING NODE_{self.node}: {agent_type} Agent")
            LOGGER.info("="*70)
            LOGGER.debug(f"Current state - Code version: {{self.state['version']}}")
            
            try:
                llm = {model}
                LOGGER.info(f"LLM assigned: {llm_agent}")
            except Exception as e:
                LOGGER.error(f"LocalLLM init failed: {{e}}")
                raise 

            # Create an Agent
            agent_name = Agent(
                role=f"""{role}""",
                goal=f"""{goal}""",
                backstory=f"""{backstory}""",
                tools=[{tool}],
                llm=llm,
                verbose=False,
            )
            LOGGER.info(f"Agent created with role: {{agent_name.role}}")

            # Define the Task
            task = Task(description=f"""{task}""",  # IF CODER, FIXERR add message? Only from de actaul code_version
                agent=agent_name,
                expected_output='any',
                )
            LOGGER.info("Task defined, sending to LLM...")

            # Execute the task with structured output format
            result = task.execute_sync()
            LOGGER.info("Task execution completed")
            result = result.raw  # Get raw text output
            # Save result according to agent type
            {save_var}

            self.update_steps()
            LOGGER.info(f"NODE_{self.node} completed successfully")
            LOGGER.info("="*70)
            return "agent_node_return_placeholder" #Provisional
        ''').strip()

def gen_compiler(self):
    return textwrap.dedent(f'''
        def node_{self.node}(self):
            LOGGER.info("="*70)
            LOGGER.info(f"ENTERING NODE_{self.node}: COMPILER/VALIDATOR")
            LOGGER.info("="*70)
            LOGGER.info(f"Validating code version {{self.state['version']}}")
            
            def validate_code(self) -> tuple:
                results = []
                self.state["syntax_valid"] = False
                self.state["execution_valid"] = False
                self.state["error"] = None
    
                if not self.state.get("code"):
                    LOGGER.warning("No candidate code to validate")
                    return results

                with NamedTemporaryFile(suffix=".py", delete=False) as temp_file:
                    temp_file.write(self.state["code"].encode())
                    temp_file_name = temp_file.name
                LOGGER.debug(f"Temporary file created: {{temp_file_name}}")

                try:
                    LOGGER.info("Checking syntax...")

                    syntax_result = subprocess.run( #Only syntax check
                        ["python", "-m", "py_compile", temp_file_name],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    syntax_valid = syntax_result.returncode == 0
                    self.state["syntax_valid"] = syntax_valid

                    if syntax_valid:
                        LOGGER.info("✓ Syntax validation passed")
                        LOGGER.info("Executing code...")

                        exec_result = subprocess.run( #if syntax is valid, execute the code
                            ["python", temp_file_name],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        execution_valid = exec_result.returncode == 0
                        self.state["execution_valid"] = execution_valid
                        
                        if execution_valid:
                            LOGGER.info("✓ Execution successful")
                            LOGGER.debug(f"Output: {{exec_result.stdout}}")
                            self.state["code"] = self.state["code"]
                            self.state["version"] += 1
                            msg = f"Valid compilation and execution for code version {{self.state['version']}}"
                            valid = True
                        else:
                            self.state["error"] = exec_result.stderr
                            msg = f"Execution failed for code version {{self.state['version']}}:\\n{{exec_result.stderr}}"
                            LOGGER.error(f"✗ Execution failed: {{exec_result.stderr}}")
                            valid = False
                    else:
                        self.state["error"] = syntax_result.stderr
                        msg = f"Syntax error in code version {{self.state['version']}}:\\n{{syntax_result.stderr}}"
                        LOGGER.error(f"✗ Syntax error: {{syntax_result.stderr}}")
                        valid = False


                
                except subprocess.TimeoutExpired:
                    self.state["error"] = "Timeout expired"
                    self.state["syntax_valid"] = False
                    self.state["execution_valid"] = False
                    msg = "Execution timeout"
                    LOGGER.error("✗ Execution timeout")
                    valid = False

                except Exception as e:
                    self.state["error"] = str(e)
                    self.state["syntax_valid"] = False
                    self.state["execution_valid"] = False
                    msg = f"Unexpected error: {{str(e)}}"
                    LOGGER.error(f"✗ Unexpected error: {{str(e)}}")
                    valid = False

                finally:
                    os.unlink(temp_file_name)
                    LOGGER.debug("Temporary file cleaned up")

                return valid

            valid_code = validate_code(self)
            self.update_steps()
            LOGGER.info(f"Validation summary - Syntax: {{self.state['syntax_valid']}}, Execution: {{self.state['execution_valid']}}, Error: {{self.state['error'] }}")
            LOGGER.info(f"NODE_{self.node} completed")
            LOGGER.info("="*70)
            
            return valid_code
        ''').strip()

def get_condition(condition):
    condition_type = condition['children'][0]['value']

    if condition_type == "EXECUTION_VALID":
        condition = "execution_valid"
    elif condition_type == "SYNTAX_VALID":
        condition = "syntax_valid"
    elif condition_type == "ERROR":
        condition = "error"
    return condition
def get_end(self):
    return textwrap.dedent(f'''
        def node_{self.node}(self):
            LOGGER.info("="*70)
            LOGGER.info(f"ENTERING NODE_{self.node}: WORKFLOW END")
            LOGGER.info("="*70)
            LOGGER.info(f"Final code version: {{self.state['version']}}")
            LOGGER.info(f"Total steps executed: {{self.steps}}")
            LOGGER.info(f"Final status - Syntax valid: {{self.state['syntax_valid']}}, Execution valid: {{self.state['execution_valid']}}")
            LOGGER.info(f"Final status  - Error: {{self.state['error']}}")

            LOGGER.info(f"Returning final code:\\n{{self.state['code']}}")
            LOGGER.info("="*70)
            return self.state['code']
        ''').strip()

class CrewaiCompiler:
    def indent_fun(self, code: str, level: int = 1) -> str:
        prefix = " " * (level * 4)
        return "\n".join(
            prefix + line if line.strip() else line
            for line in code.splitlines()
        )

    def __init__(self, ind_id, diagram, path, llm_usage=True, agent_config='Fixed', 
                 llm_type='LOCAL', model_family=None, gpu=None, direct_llm=None):
        self.path = path
        self.llm_usage = llm_usage
        self.llm_type = llm_type
        self.agent_config = agent_config
        self.diagram = diagram
        self.code_lines = []
        self.node=0
        self.model_family = model_family
        self.gpu = gpu
        self.direct_llm = direct_llm
        if not QUIET_COMPILER_LOGS:
            print(f"[DEBUG INIT] Compiler initialized for individual {ind_id}, output path: {path}")
            print(f"[DEBUG INIT] LLM usage: {llm_usage}, agent config: {agent_config}, LLM type: {llm_type}, Model family: {model_family}, gpu: {gpu}")

    def generate_nodes(self):
        
        self.node = 0
        self.all_nodes=0
        node_lines = []
        code_chunks_general = []

        submethods = textwrap.dedent(f'''
    def update_steps(self):
        self.steps += 1
        LOGGER.debug(f"Step counter updated:{{self.steps}}/{{self.max_steps}}")
        
        if self.steps >= self.max_steps:
            LOGGER.warning(f"Maximum steps reached ({{self.max_steps}}). Finishing workflow.")
            return 'finish'
    def run_flow(self):
        result = "__'RESULT_PLACEHOLDER__"
        start_time = time.time()
        TIMEOUT = 120
        def check_timeout(node_name):
            if time.time() - start_time > TIMEOUT:
                LOGGER.error(f"TIMEOUT IN NODE {{node_name}}, more than {{TIMEOUT}}s")
            return "__'TIMEOUT_PLACEHOLDER__"
                                     
                      ''').strip()
        flow_lines = [
            self.indent_fun(submethods, level=1)
        ]       
            
        def traverse(self, node, indent=1):
            prefix = " " * ((indent+1) * 4)  # 4 espacios por nivel
            prefix2 = " " * ((indent+2) * 4)  # 4 espacios por nivel
            code_chunks = []
            flow_chunks = []
            if node["value"] == "SIMPLE_CONDITIONAL": 
                cond = get_condition(node['children'][1])
                flow_chunks.append(f"{prefix}if self.state['{cond}']:")
                then_children = [
                    child for child in node.get("children", [])
                    if child.get("value") not in ("CONDITION", "ELSE")
                ]

                def emit_branch_or_pass(branch_node, branch_indent):
                    branch_code, branch_flow = traverse(self, branch_node, branch_indent)
                    if branch_flow:
                        return branch_code, branch_flow
                    return [], [f"{' ' * ((branch_indent + 1) * 4)}pass"]

                if then_children:
                    # hijos del THEN indentados un nivel más
                    for child in then_children:
                        if isinstance(child, dict) and child.get("value") == "WORKFLOW" and not child.get("children"):
                            child_code, child_flow = [], [f"{prefix2}pass"]
                        else:
                            child_code, child_flow = emit_branch_or_pass(child, indent + 1)
                        code_chunks.extend(child_code)
                        flow_chunks.extend(child_flow)
                else:
                    # Evita generar un bloque if vacío inválido
                    flow_chunks.append(f"{prefix2}pass")

                # Procesar rama ELSE explícita (si existe)
                for child in node.get("children", []):
                    if child.get("value") == "ELSE":
                        child_code, child_flow = traverse(self, child, indent + 1)
                        code_chunks.extend(child_code)
                        flow_chunks.extend(child_flow)
                        if not child.get("children"):
                            flow_chunks.append(f"{prefix2}pass")

            elif node["value"] == 'ELSE':
                prefix_else = " " * ((indent) * 4)
                flow_chunks.append(f"{prefix_else}else:")
                for child in node.get("children", []):
                    child_code, child_flow = traverse(self, child, indent + 1)
                    code_chunks.extend(child_code)
                    flow_chunks.extend(child_flow)

            else:
                if node["value"] == "AGENT":
                    code_chunks.append(gen_agent(self, node['children'], self.llm_type, self.model_family, self.gpu))
                    flow_chunks.append(f"{prefix}check_timeout({self.node})")
                    flow_chunks.append(f"{prefix}result=node_{self.node}(self)")
                    flow_chunks.append(f"{prefix}self.save_code_history()")

                    self.node += 1

                    if node['children'][0]['value'].startswith(('CODER', 'FIXER')):
                        code_chunks.append(gen_compiler(self))
                        flow_chunks.append(f"{prefix}check_timeout({self.node})")
                        flow_chunks.append(f"{prefix}valid_code = node_{self.node}(self)")
                        flow_chunks.append(f"{prefix}self.save_code_history()")
                        flow_chunks.append(f"{prefix}if valid_code:") # La primera vez que consigamos un codigo valido lo devolvemos
                        flow_chunks.append(f"{prefix2}return self.state['code']")
                        self.node += 1

                elif node["value"] == "END":
                    code_chunks.append(get_end(self))
                    flow_chunks.append(f"{prefix}check_timeout({self.node})")
                    flow_chunks.append(f"{prefix}result=node_{self.node}(self)")
                    flow_chunks.append(f"{prefix}self.save_code_history()")

                    self.node += 1


                for child in node.get("children", []):
                    child_code, child_flow = traverse(self, child, indent)
                    code_chunks.extend(child_code)
                    flow_chunks.extend(child_flow)


            return code_chunks,flow_chunks

        node_lines, flow_chunks = traverse(self, self.diagram)
        
        #Finish
        flow_chunks.append(" " * 4 * 2 + f"check_timeout({self.node})")
        flow_chunks.append(" " * 4 * 2 + f"result=node_{self.node}(self)")
        # Keep run logs clean: do not print generated code to stdout.
        # flow_chunks.append(" " * 4 * 2 + "print(result)")
        flow_chunks.append(" " * 4 * 2 + "return result")

        node_lines.extend(get_end(self).splitlines()) 
        flow_lines.extend(flow_chunks)
        return node_lines, flow_lines



    def compile(self, output_file):
        output_dir = os.path.dirname(output_file)
        os.makedirs(output_dir, exist_ok=True)

        init_lines = gen_init()
        node_lines, flow_lines = self.generate_nodes()
        code = "\n\n".join([init_lines] + flow_lines +node_lines)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(code)
        #print(f"Code written to {output_file}")