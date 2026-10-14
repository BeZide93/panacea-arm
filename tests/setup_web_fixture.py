"""Browser-test server with temporary fake Wine; never uses a real Steam prefix."""
import json
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'linux-setup/assistant'))
from test_setup_assistant import Execution
import web
from setup_profile import Profile

fixture=Execution(methodName='runTest')
fixture.setUp()
profile=Profile(fixture.steam,fixture.game,fixture.targets[0].compat,fixture.root/'backups',fixture.proton,'Temporäre Testeinrichtung')
app=web.Application(fixture.root)
app.state_dir=fixture.root/'state'
try:
    with patch('web.load_profile',return_value=profile), patch('web.require_stopped'), patch('core.require_stopped'):
        with web.Server(app) as server:
            print(json.dumps({'url':server.origin+'/#'+server.token}),flush=True)
            server.serve_forever()
finally:
    fixture.tearDown()
