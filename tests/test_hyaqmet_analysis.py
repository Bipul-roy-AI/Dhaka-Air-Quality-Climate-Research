from pathlib import Path
import importlib.util
import unittest
import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('hyaqmet_analysis',Path(__file__).resolve().parents[1]/'scripts/analyze_hyaqmet.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class HyAQMetAnalysisTests(unittest.TestCase):
    def test_published_boundaries_include_leap_year_dates(self):
        dates=pd.to_datetime(['2020-02-15','2020-02-16','2020-04-15','2020-04-16','2020-06-15','2020-06-16','2020-10-15','2020-10-16','2020-11-15','2020-11-16','2020-12-15','2020-12-16'])
        self.assertEqual(m.season_labels(dates).tolist(),['Winter','Spring','Spring','Summer','Summer','Monsoon','Monsoon','Autumn','Autumn','Late Autumn','Late Autumn','Winter'])
    def test_notebook_and_paper_conflict_stays_visible(self):
        dates=pd.to_datetime(['2021-08-16','2021-10-15','2021-12-15'])
        self.assertEqual(m.season_labels(dates).tolist(),['Monsoon','Monsoon','Late Autumn'])
        self.assertEqual(m.season_labels(dates,'notebook').tolist(),['Autumn','Late Autumn','Winter'])
    def test_zero_or_negative_blh_never_becomes_valid_by_clipping(self):
        out=m.scale_by_blh([10,10,10,10],[0,-1,25,100],100,50)
        self.assertTrue(np.isnan(out[:2]).all());np.testing.assert_allclose(out[2:],[20,10])
        with self.assertRaises(ValueError):m.scale_by_blh([1],[0])
    def test_hourly_amount_sum_is_not_daily_cumulative_repair(self):
        index=pd.date_range('2020-01-01',periods=48,freq='h')
        amounts=np.ones(48);self.assertEqual(m.annual_amount_sums(amounts,index).loc[2020],48)
        cumulative=np.tile(np.arange(1,25),2)
        self.assertEqual(m.annual_amount_sums(cumulative,index).loc[2020],600)
        # Expected daily totals48; the diagnostic must expose overcount, not fix it.
    def test_pair_metrics_sign_and_identity_r2(self):
        x=m.pair_metrics([2,3,4],[1,2,3]);self.assertEqual(x['bias_a_minus_b'],1);self.assertEqual(x['RMSE'],1)
        self.assertAlmostEqual(x['Pearson_r'],1);self.assertLess(x['identity_R2_a_reference'],1)
    def test_centered_vif_identifies_exact_duplicate_predictors(self):
        frame=pd.DataFrame({'a':[1,2,3,4],'b':[2,4,6,8]})
        out=m.vif_table(frame);self.assertTrue(np.isinf(out.VIF).all())


class PaperTraceTests(unittest.TestCase):
    def test_claim_table_preserves_disagreement_and_does_not_invent_candidate_count(self):
        qc={'rows':52584,'columns_including_timestamp':42,'missing_by_column':{'x':0},'missing_expected_hours':0,'unexpected_hours':0,'released_season_codes':[1,2,3,4,5,6],'released_vs_paper_table3_label_disagreements':13968}
        data=pd.DataFrame({'cams_pm25_ugm3':[102.30,102.366]})
        deciles=pd.DataFrame({'pm25_mean_ugm3':[30.36,10]})
        association=[{'scale':'hourly_unadjusted','Pearson_r':-.4904}]
        result=m.paper_vs_reproduced(qc,data,deciles,association).set_index('result')
        self.assertEqual(result.loc['BLH_PM25_Pearson_r','match_status'],'not_reproduced_at_reported_precision')
        self.assertEqual(result.loc['CAMS_PM25_mean_2017_2022','match_status'],'reproduced_at_reported_precision')
        self.assertEqual(result.loc['MERRA_candidate_to_retained_count','match_status'],'not_assessed')
        self.assertEqual(result.loc['season_label_disagreements_with_Table3','reproduced_value'],13968)
        self.assertEqual(result.loc['season_codes','match_status'],'not_reproduced')

class PublicationExportTests(unittest.TestCase):
    def test_figure_exports_png_editable_svg_and_figure_pdf(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            figure,axes=m.plt.subplots(figsize=(2,2));axes.plot([0,1],[0,1]);axes.set_xlabel('Test axis')
            m._save_figure(figure,Path(directory),'diagnostic',300)
            self.assertTrue((Path(directory)/'diagnostic.png').read_bytes().startswith(b'\x89PNG'))
            self.assertTrue((Path(directory)/'diagnostic.pdf').read_bytes().startswith(b'%PDF'))
            self.assertIn('<text', (Path(directory)/'diagnostic.svg').read_text())
            m.plt.close(figure)
    def test_invalid_dpi_rejected_before_data_or_outputs_are_touched(self):
        with self.assertRaisesRegex(ValueError,'figure_dpi'):
            m.analyze('missing.csv','missing-source','missing-output',72)

if __name__=='__main__':unittest.main()
