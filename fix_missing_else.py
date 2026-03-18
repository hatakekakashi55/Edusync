import codecs
import re

file_path = r'c:\Users\wayne\Documents\edusync-babu\communication_stage.html'
with codecs.open(file_path, 'r', 'utf-8') as f:
    text = f.read()

def inject_else_block(text, fetch_pattern, block_to_inject):
    # Find the end of the `if (response.ok) { ... }` block
    # By replacing `} catch (e)` with `} else { throw new Error(...); } } catch (e)`
    # But only if it misses it.
    pass

# We will just inject an else { throw new Error(response.statusText); } right before } catch (e)
# It's safer to just replace `} catch (e) {` with `} else { throw new Error('API Error'); } } catch (e) {`
# but only for these 4 functions.

funcs = ['startDirectionFollower', 'evaluateDirection', 'startToneRecognizer', 'evaluateTone', 'submitFillBeats', 'startFillBeats']

for func in funcs:
    # Match the function body until the first `} catch (e) {` or `} catch (error) {`
    # We'll use regex to find the response.ok block end.
    
    # Actually, replacing `} catch (e) {` blindly in the whole function might replace the wrong one if there are multiple, but these are small functions.
    pattern = r"(async function " + func + r"\b.*?)(?=\}\s*catch\s*\([^\)]+\)\s*\{)"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        func_content = match.group(1)
        if "else {" not in func_content.split("response.ok")[1] if "response.ok" in func_content else "":
            # Inject else block before the catch
            new_content = func_content + "} else { throw new Error('Server returned ' + response.status); \n                "
            text = text.replace(func_content, new_content)

with codecs.open(file_path, 'w', 'utf-8') as f:
    f.write(text)

print("Injected else blocks for error handling.")
