import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from dhaka_air_quality.__main__ import main

class CliTests(unittest.TestCase):
    def test_complete_run_preserves_input_and_prior_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);raw=root/'input.csv';out=root/'out'
            t=pd.date_range('2023-01-01','2023-03-31 23:00',freq='h')
            pd.DataFrame({'city_name':'Dhaka','datetime':t,'pm2_5':20+np.sin(np.arange(len(t))/24),'pm10':50,'lat':float('nan'),'lon':90.4}).to_csv(raw,index=False)
            before=hashlib.sha256(raw.read_bytes()).hexdigest()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--input',str(raw),'--output',str(out),'--min-train-months','2','--no-figure']),0)
            self.assertEqual(before,hashlib.sha256(raw.read_bytes()).hexdigest())
            rebuilt=pd.read_csv(out/'monthly_rebuilt.csv')
            self.assertEqual(len(rebuilt),3)
            source=json.loads((out/'source_audit.json').read_text())
            self.assertIsNone(source['recorded_coordinates'][0]['lat'])
            self.assertTrue(rebuilt.complete_month.all())
            audit=json.loads((out/'evaluation_audit.json').read_text())
            self.assertEqual(audit['scored_forecast_months'],1)
            manifest=json.loads((out/'run_manifest.json').read_text())
            self.assertIsNone(manifest['source_attribution']['doi'])
            saved=(out/'predictions.csv').read_bytes()
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                main(['--input',str(raw),'--output',str(out),'--no-figure'])
            self.assertEqual(saved,(out/'predictions.csv').read_bytes())
    def test_invalid_input_does_not_create_success_artifacts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);raw=root/'bad.csv';out=root/'out'
            raw.write_text('city_name,datetime,pm2_5\nDhaka,not-a-date,20\n')
            with self.assertRaises(ValueError):main(['--input',str(raw),'--output',str(out),'--no-figure'])
            self.assertFalse(out.exists())

    def test_failed_render_does_not_publish_partial_run(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);raw=root/'input.csv';out=root/'out'
            raw.write_text('city_name,datetime,pm2_5\nDhaka,2023-01-01T00:00,20\n')
            with patch('dhaka_air_quality.__main__._plot',side_effect=RuntimeError('render failed')):
                with self.assertRaisesRegex(RuntimeError,'render failed'):
                    main(['--input',str(raw),'--output',str(out)])
            self.assertFalse(out.exists())
            self.assertEqual(list(root.glob('.out-*')),[])

if __name__=='__main__':unittest.main()
