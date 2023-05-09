# Author: Simon Liedtke <liedtke.simon@googlemail.com>
#
# This module was developed with funding provided by
# the Google Summer of Code (2013).

import os
from datetime import datetime
from collections.abc import Hashable

import numpy as np
import pytest

import astropy.units as u
from astropy import conf

from sunpy.data.test import get_test_filepath
from sunpy.data.test import rootdir as testdir
from sunpy.database import Database
from sunpy.database.tables import (
    DatabaseEntry,
    FitsHeaderEntry,
    FitsKeyComment,
    Tag,
    WaveunitNotFoundError,
    _create_display_table,
    entries_from_dir,
    entries_from_fido_search_result,
    entries_from_file,
    entries_from_query_result,
)
from sunpy.net import Fido
from sunpy.net import attrs as net_attrs
from sunpy.net import vso

RHESSI_IMAGE = get_test_filepath('hsi_image_20101016_191218.fits')
GOES_DATA = get_test_filepath('go1520110607.fits')


@pytest.fixture
def mq_image(waveunit_fits_directory):
    fits_files = waveunit_fits_directory.glob('*.fits')
    return os.fspath([f for f in fits_files if f.name == 'mq130812.084253.fits'][0])


@pytest.fixture
def eit_195_image(eit_fits_directory):
    fits_files = eit_fits_directory.glob('*.fits')
    return os.fspath([f for f in fits_files if f.name == 'efz20040301.000010_s.fits'][0])


@pytest.fixture
def fido_search_result():
    # A search query with responses from all instruments
    # No JSOC query
    return Fido.search(
        net_attrs.Time("2012/1/1", "2012/1/2"),
        net_attrs.Instrument('lyra') & net_attrs.Level.two | net_attrs.Instrument('eve') |
        net_attrs.Instrument('XRS') | net_attrs.Instrument('noaa-indices') |
        net_attrs.Instrument('noaa-predict') |
        (net_attrs.Instrument('norh') & net_attrs.Wavelength(17 * u.GHz)) |
        (net_attrs.Instrument('rhessi') & net_attrs.Physobs("summary_lightcurve"))
    )


@pytest.fixture
def query_result():
    client = vso.VSOClient()
    return client.search(net_attrs.Time('2001/1/1', '2001/1/2'),
                         net_attrs.Instrument('EIT'),
                         response_format="legacy")


@pytest.fixture
def qr_with_none_waves():
    return vso.VSOClient().search(
        net_attrs.Time('20121224T120049.8', '20121224T120049.8'),
        net_attrs.Provider('SDAC'), net_attrs.Instrument('VIRGO'),
        response_format="legacy")


@pytest.fixture
def qr_block_with_missing_physobs():
    return vso.VSOClient().search(
        net_attrs.Time('20130805T120000', '20130805T121000'),
        net_attrs.Instrument('SWAVES'), net_attrs.Source('STEREO_A'),
        net_attrs.Provider('SSC'), net_attrs.Wavelength(
            10 * u.kHz, 160 * u.kHz),
        response_format="legacy")[0]


@pytest.fixture
def qr_block_with_kev_unit():
    return vso.VSOClient().search(
        net_attrs.Time((2011, 9, 20, 1), (2011, 9, 20, 2)),
        net_attrs.Instrument('RHESSI'),
        response_format="legacy")[0]


def test_fits_header_entry_equality():
    assert FitsHeaderEntry('key', 'value') == FitsHeaderEntry('key', 'value')
    assert not (FitsHeaderEntry('key', 'value') == FitsHeaderEntry('k', 'v'))


def test_fits_header_entry_inequality():
    assert FitsHeaderEntry('key', 'value') != FitsHeaderEntry('k', 'v')
    assert not (FitsHeaderEntry('k', 'v') != FitsHeaderEntry('k', 'v'))


def test_fits_header_entry_hashability():
    assert isinstance(FitsHeaderEntry('key', 'value'), Hashable)


def test_tag_equality():
    assert Tag('abc') == Tag('abc')
    assert not (Tag('abc') == Tag('xyz'))


def test_tag_inequality():
    assert Tag('abc') != Tag('xyz')
    assert not (Tag('abc') != Tag('abc'))


def test_tag_hashability():
    assert isinstance(Tag(''), Hashable)


@pytest.mark.remote_data
def test_entries_from_fido_search_result(fido_search_result):
    entries = list(entries_from_fido_search_result(fido_search_result))
    # 68 entries for 8 instruments in fido_search_result
    assert len(entries) == 68
    # First 2 entries are from lyra
    assert entries[0] == DatabaseEntry(
        source='PROBA2', provider='ESA', physobs='irradiance',
        fileid='http://proba2.oma.be/lyra/data/bsd/2012/01/01/lyra_20120101-000000_lev2_std.fits',
        observation_time_start=datetime(2012, 1, 1, 0, 0),
        observation_time_end=datetime(2012, 1, 1, 23, 59, 59, 999000),
        wavemin=np.nan, wavemax=np.nan,
        instrument='LYRA')
    # 2 entries from eve, level 0
    assert entries[2] == DatabaseEntry(
        source='SDO', provider='LASP', physobs='irradiance',
        fileid=("http://lasp.colorado.edu/eve/data_access/evewebdata/quicklook"
                "/L0CS/SpWx/2012/20120101_EVE_L0CS_DIODES_1m.txt"),
        observation_time_start=datetime(2012, 1, 1, 0, 0),
        observation_time_end=datetime(2012, 1, 1, 23, 59, 59, 999000),
        wavemin=np.nan, wavemax=np.nan,
        instrument='EVE')
    # 56 entries from EVE
    assert entries[4] == DatabaseEntry(
        source='SDO', provider='LASP', physobs='irradiance',
        fileid='EVE_L1_esp_2012001_00',
        observation_time_start=datetime(2012, 1, 1, 0, 0),
        observation_time_end=datetime(2012, 1, 2, 0, 0),
        size=None,
        instrument='EVE',
        wavemin=0.1, wavemax=30.4)
    # 2 entries from goes
    assert entries[60] == DatabaseEntry(
        source='GOES', provider='NOAA', physobs='irradiance',
        fileid='https://www.ncei.noaa.gov/data/goes-space-environment-monitor/access/science/xrs/goes15/'
               'gxrs-l2-irrad_science/2012/01/sci_gxrs-l2-irrad_g15_d20120101_v0-0-0.nc',
        observation_time_start=datetime(2012, 1, 1, 0, 0),
        observation_time_end=datetime(2012, 1, 1, 23, 59, 59, 999000),
        wavemin=np.nan, wavemax=np.nan,
        instrument='XRS')
    # 1 entry from noaa-indices
    assert entries[62] == DatabaseEntry(
        source='SIDC', provider='SWPC', physobs='sunspot number',
        fileid='https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json',
        observation_time_start=None,
        observation_time_end=None,
        wavemin=np.nan, wavemax=np.nan,
        instrument='NOAA-Indices')
    # 1 entry from noaa-predict
    assert entries[63] == DatabaseEntry(
        source='ISES', provider='SWPC', physobs='sunspot number',
        fileid='https://services.swpc.noaa.gov/json/solar-cycle/predicted-solar-cycle.json',
        observation_time_start=None,
        observation_time_end=None,
        wavemin=np.nan, wavemax=np.nan,
        instrument='NOAA-Predict')
    # 2 entries from norh
    assert entries[64] == DatabaseEntry(
        source='NAOJ', provider='NRO', physobs=None,
        fileid=("ftp://solar-pub.nao.ac.jp/"
                "pub/nsro/norh/data/tcx/2012/01/tca120101"),
        observation_time_start=datetime(2012, 1, 1, 0, 0),
        observation_time_end=datetime(2012, 1, 1, 23, 59, 59, 999000),
        wavemin=17634850.470588233, wavemax=17634850.470588233,
        instrument='NORH')
    # 2 entries from rhessi
    assert 'hsi_obssumm_20120101' in entries[66].fileid
    assert entries[66] == DatabaseEntry(
        source="RHESSI", provider='NASA', physobs='summary_lightcurve',
        fileid=entries[66].fileid,
        observation_time_start=datetime(2012, 1, 1, 0, 0),
        observation_time_end=datetime(2012, 1, 1, 23, 59, 59, 999000),
        wavemin=np.nan, wavemax=np.nan,
        instrument='RHESSI')


@pytest.mark.remote_data
def test_entries_from_fido_search_result_JSOC():
    search_result = Fido.search(
        net_attrs.Time('2014-01-01T00:00:00', '2014-01-01T01:00:00'),
        net_attrs.jsoc.Series('hmi.m_45s'),
        net_attrs.jsoc.Notify("sunpy@sunpy.org")
    )
    with pytest.raises(ValueError):
        # Using list() here is important because the
        # entries_from_fido_search_result function uses yield.
        # list() uses the generator to run the function body.
        list(entries_from_fido_search_result(search_result))


@pytest.mark.remote_data
def test_from_fido_search_result_block(fido_search_result):
    entry = DatabaseEntry._from_fido_search_result_block(
        fido_search_result[0, 0])
    expected_entry = DatabaseEntry(
        source='PROBA2', provider='ESA', physobs='irradiance',
        fileid='http://proba2.oma.be/lyra/data/bsd/2012/01/01/lyra_20120101-000000_lev2_std.fits',
        observation_time_start=datetime(2012, 1, 1, 0, 0),
        observation_time_end=datetime(2012, 1, 1, 23, 59, 59, 999000),
        wavemin=np.nan, wavemax=np.nan,
        instrument='LYRA')
    assert entry == expected_entry


@pytest.mark.remote_data
def test_entry_from_qr_block(query_result):
    entry = DatabaseEntry._from_query_result_block(query_result.blocks[0])
    expected_entry = DatabaseEntry(
        source='SOHO', provider='SDAC', physobs='intensity',
        fileid='/archive/soho/private/data/processed/eit/lz/2001/01/efz20010101.000042',
        observation_time_start=datetime(2001, 1, 1, 0, 0, 42),
        observation_time_end=datetime(2001, 1, 1, 0, 0, 54),
        instrument='EIT', size=2059.0, wavemin=19.5, wavemax=19.5)
    assert entry == expected_entry


@pytest.mark.remote_data
def test_entry_from_qr_block_with_missing_physobs(qr_block_with_missing_physobs):
    entry = DatabaseEntry._from_query_result_block(
        qr_block_with_missing_physobs.blocks[0])
    expected_entry = DatabaseEntry(
        source='STEREO_A', provider='SSC',
        fileid='swaves/2013/swaves_average_20130805_a_hfr.dat',
        observation_time_start=datetime(2013, 8, 5),
        observation_time_end=datetime(2013, 8, 6), instrument='SWAVES',
        size=3601.08, wavemin=2398339664000.0, wavemax=18737028625.0)
    assert entry == expected_entry


@pytest.mark.remote_data
def test_entry_from_qr_block_kev(qr_block_with_kev_unit):
    # See issue #766.
    entry = DatabaseEntry._from_query_result_block(
        qr_block_with_kev_unit.blocks[0])
    assert entry.source == 'RHESSI'
    assert entry.provider == 'LSSP'
    assert entry.fileid in ['/hessidata/2011/09/19/hsi_20110919_233340_002.fits',
                            "/hessidata/2011/09/20/hsi_20110920_010920_001.fits"]
    assert entry.observation_time_start in [
        datetime(2011, 9, 19, 23, 33, 40), datetime(2011, 9, 20, 1, 9, 20)]
    assert entry.observation_time_end in [
        datetime(2011, 9, 20, 1, 9, 20), datetime(2011, 9, 20, 2, 27, 40)]
    assert entry.instrument == 'RHESSI'
    assert round(entry.wavemin, 3) == 0.413
    assert round(entry.wavemax, 7) == 0.0000729


def test_entries_from_file(mq_image):
    entries = list(entries_from_file(mq_image))
    assert len(entries) == 1
    entry = entries[0]
    assert len(entry.fits_header_entries) == 31
    expected_fits_header_entries = [
        FitsHeaderEntry('SIMPLE', True),
        FitsHeaderEntry('BITPIX', 16),
        FitsHeaderEntry('NAXIS', 2),
        FitsHeaderEntry('NAXIS1', 1500),
        FitsHeaderEntry('NAXIS2', 1340),
        FitsHeaderEntry('CONTACT', 'Isabelle.Buale@obspm.fr'),
        FitsHeaderEntry('DATE_OBS', '2013-08-12T08:42:53.000'),
        FitsHeaderEntry('DATE_END', '2013-08-12T08:42:53.000'),
        FitsHeaderEntry('FILENAME', 'mq130812.084253.fits'),
        FitsHeaderEntry('INSTITUT', 'Observatoire de Paris'),
        FitsHeaderEntry('INSTRUME', 'Spectroheliograph'),
        FitsHeaderEntry('OBJECT', 'FS'),
        FitsHeaderEntry('OBS_MODE', 'SCAN'),
        FitsHeaderEntry('PHYSPARA', 'Intensity'),
        FitsHeaderEntry('NBREG', 1),
        FitsHeaderEntry('NBLAMBD', 1),
        FitsHeaderEntry('WAVELNTH', 6563),
        FitsHeaderEntry('WAVEUNIT', 'angstrom'),
        FitsHeaderEntry('POLARANG', 0),
        FitsHeaderEntry('THEMISFF', 3),
        FitsHeaderEntry('LONGTRC', 258.78),
        FitsHeaderEntry('LONGCARR', 258.78),
        FitsHeaderEntry('LONGITUD', 258.78),
        FitsHeaderEntry('LATITUD', 6.50107),
        FitsHeaderEntry('LATIRC', 6.50107),
        FitsHeaderEntry('INDLAMD', 1),
        FitsHeaderEntry('INDREG', 1),
        FitsHeaderEntry('SEQ_IND', 1),
        FitsHeaderEntry('SVECTOR', 0),
        FitsHeaderEntry('COMMENT', ''),
        FitsHeaderEntry('HISTORY', '')]
    assert entry.fits_header_entries == expected_fits_header_entries
    assert entry.fits_key_comments.sort() == [
        FitsKeyComment('SIMPLE', 'Written by IDL:  Mon Aug 12 08:48:08 2013'),
        FitsKeyComment('BITPIX', 'Integer*2 (short integer)')].sort()
    assert entry.instrument == 'Spectroheliograph'
    assert entry.observation_time_start == datetime(2013, 8, 12, 8, 42, 53)
    assert entry.observation_time_end == datetime(2013, 8, 12, 8, 42, 53)
    assert round(entry.wavemin, 1) == 656.3
    assert round(entry.wavemax, 1) == 656.3
    assert entry.path == mq_image


def test_entries_from_file_withoutwaveunit(eit_195_image):
    # does not raise `WaveunitNotFoundError`, because no wavelength information
    # is present in this file
    next(entries_from_file(RHESSI_IMAGE))
    with pytest.raises(WaveunitNotFoundError):
        next(entries_from_file(eit_195_image))


def test_entries_from_file_time_string_parse_format():

    with pytest.raises(ValueError):
        # Error should be  raised because of the date format in GOES_DATA
        entries = list(entries_from_file(GOES_DATA))

    entries = list(entries_from_file(GOES_DATA,
                                     time_string_parse_format='%d/%m/%Y'))

    assert len(entries) == 4
    entry = entries[0]
    assert len(entry.fits_header_entries) == 16

    assert entry.observation_time_start == datetime(2011, 6, 7, 0, 0)
    assert entry.observation_time_end == datetime(2011, 6, 7, 0, 0)
    assert entry.path == GOES_DATA


def test_entries_from_dir(waveunit_fits_directory):
    entries = list(entries_from_dir(waveunit_fits_directory, time_string_parse_format='%d/%m/%Y', pattern='*fits'))
    assert len(entries) == 4
    for entry, filename in entries:
        if filename.endswith('na120701.091058.fits'):
            break
    assert entry.path in (os.path.join(waveunit_fits_directory, filename), filename)
    assert filename.startswith(os.fspath(waveunit_fits_directory))
    assert len(entry.fits_header_entries) == 40
    assert entry.fits_header_entries == [
        FitsHeaderEntry('SIMPLE', True),
        FitsHeaderEntry('BITPIX', -32),
        FitsHeaderEntry('NAXIS', 3),
        FitsHeaderEntry('NAXIS1', 256),
        FitsHeaderEntry('NAXIS2', 256),
        FitsHeaderEntry('NAXIS3', 1),
        FitsHeaderEntry('DATE', '27-OCT-82'),
        FitsHeaderEntry('DATE-OBS', '2012-07-01'),
        FitsHeaderEntry('DATE_OBS', '2012-07-01T09:10:58.200Z'),
        FitsHeaderEntry('DATE_END', '2012-07-01T09:10:58.200Z'),
        FitsHeaderEntry('WAVELNTH', 1.98669),
        FitsHeaderEntry('WAVEUNIT', 'm'),
        FitsHeaderEntry('PHYSPARA', 'STOKESI'),
        FitsHeaderEntry('OBJECT', 'FS'),
        FitsHeaderEntry('OBS_TYPE', 'RADIO'),
        FitsHeaderEntry('OBS_MODE', 'IMAGE'),
        FitsHeaderEntry('LONGITUD', 0.0),
        FitsHeaderEntry('LATITUDE', 0.0),
        FitsHeaderEntry('INSTITUT', 'MEUDON'),
        FitsHeaderEntry('CMP_NAME', 'ROUTINE'),
        FitsHeaderEntry('CONTACT', ' A. KERDRAON'),
        FitsHeaderEntry('TELESCOP', 'NRH'),
        FitsHeaderEntry('INSTRUME', 'NRH2'),
        FitsHeaderEntry('FILENAME', 'nrh2_1509_h80_20120701_091058c02_i.fts'),
        FitsHeaderEntry('NRH_DATA', '2DB'),
        FitsHeaderEntry('ORIGIN', 'wrfits'),
        FitsHeaderEntry('FREQ', 150.9),
        FitsHeaderEntry('FREQUNIT', 6),
        FitsHeaderEntry('BUNIT', 'K'),
        FitsHeaderEntry('EXPTIME', 1168576512),
        FitsHeaderEntry('CTYPE1', 'Solar-X'),
        FitsHeaderEntry('CTYPE2', 'Solar-Y'),
        FitsHeaderEntry('CTYPE3', 'StokesI'),
        FitsHeaderEntry('CRPIX1', 128),
        FitsHeaderEntry('CRPIX2', 128),
        FitsHeaderEntry('CDELT1', 0.015625),
        FitsHeaderEntry('CDELT2', 0.015625),
        FitsHeaderEntry('SOLAR_R', 64.0),
        FitsHeaderEntry('COMMENT', ''),
        FitsHeaderEntry('HISTORY', '')]
    assert entry.fits_key_comments.sort() == [
        FitsKeyComment('WAVEUNIT', 'in meters'),
        FitsKeyComment('NAXIS2', 'number of rows'),
        FitsKeyComment('CDELT2', 'pixel scale y, in solar radius/pixel'),
        FitsKeyComment('CRPIX1', 'SUN CENTER X, pixels'),
        FitsKeyComment('CRPIX2', 'SUN CENTER Y, pixels'),
        FitsKeyComment('SOLAR_R', 'SOLAR RADIUS, pixels'),
        FitsKeyComment('NAXIS1', 'number of columns'),
        FitsKeyComment('CDELT1', 'pixel scale x, in solar radius/pixel'),
        FitsKeyComment('NAXIS3', 'StokesI'),
        FitsKeyComment('TELESCOP', 'Nancay Radioheliograph'),
        FitsKeyComment('INSTRUME', 'Nancay 2D-images Radioheliograph'),
        FitsKeyComment('BUNIT', 'Brightness temperature'),
        FitsKeyComment('BITPIX', 'IEEE 32-bit floating point values'),
        FitsKeyComment('DATE', 'Date of file creation'),
        FitsKeyComment('FREQUNIT', 'in MHz'),
        FitsKeyComment('EXPTIME', 'in seconds')].sort()


def test_entries_from_dir_recursively_true():
    entries = list(entries_from_dir(testdir, True,
                                    default_waveunit='angstrom',
                                    time_string_parse_format='%d/%m/%Y',
                                    pattern='*fits'))
    assert len(entries) == 18


def test_entries_from_dir_recursively_false():
    entries = list(entries_from_dir(testdir, False,
                                    default_waveunit='angstrom',
                                    time_string_parse_format='%d/%m/%Y',
                                    pattern='*fits'))
    assert len(entries) == 16


@pytest.mark.remote_data
def test_entries_from_query_result(query_result):
    entries = list(entries_from_query_result(query_result))
    assert len(entries) == 122
    snd_entry = entries[1]
    expected_entry = DatabaseEntry(
        source='SOHO', provider='SDAC', physobs='intensity',
        fileid='/archive/soho/private/data/processed/eit/lz/2001/01/efz20010101.001210',
        observation_time_start=datetime(2001, 1, 1, 0, 12, 10),
        observation_time_end=datetime(2001, 1, 1, 0, 12, 23),
        instrument='EIT', size=2059.0, wavemin=19.5, wavemax=19.5)
    assert snd_entry == expected_entry


@pytest.mark.remote_data
def test_entry_from_query_results_with_none_wave(qr_with_none_waves):
    # does not raise WaveunitNotFoundError because neither wavemin nor wavemax
    # are given
    list(entries_from_query_result(qr_with_none_waves))


@pytest.mark.remote_data
def test_entry_from_query_results_with_none_wave_and_default_unit(
        qr_with_none_waves):
    entries = list(entries_from_query_result(qr_with_none_waves, 'nm'))
    expected = [
        DatabaseEntry(
            source='SOHO', provider='SDAC', physobs='intensity',
            fileid='/archive/soho/private/data/processed/virgo/tsi_full/VIRGO_TSI_daily_hourly.zip',
            observation_time_start=datetime(1995, 12, 2, 0, 0),
            observation_time_end=datetime(2020, 1, 1, 0, 0),
            instrument='VIRGO', size=13506.0),
        DatabaseEntry(
            source='SOHO', provider='SDAC', physobs='intensity',
            fileid='/archive/soho/private/data/processed/virgo/spm/VIRGO-SPM-BLUE-L2-MISSIONLONG.fits',
            observation_time_start=datetime(1996, 1, 23, 0, 0),
            observation_time_end=datetime(2021, 5, 15, 23, 59),
            instrument='VIRGO', size=32652.0),
        DatabaseEntry(
            source='SOHO', provider='SDAC', physobs='intensity',
            fileid='/archive/soho/private/data/processed/virgo/spm/VIRGO-SPM-GREEN-L2-MISSIONLONG.fits',
            observation_time_start=datetime(1996, 1, 23, 0, 0),
            observation_time_end=datetime(2021, 5, 15, 23, 59),
            instrument='VIRGO', size=32652.0),
        DatabaseEntry(
            source='SOHO', provider='SDAC', physobs='intensity',
            fileid='/archive/soho/private/data/processed/virgo/spm/VIRGO-SPM-RED-L2-MISSIONLONG.fits',
            observation_time_start=datetime(1996, 1, 23, 0, 0),
            observation_time_end=datetime(2021, 5, 15, 23, 59),
            instrument='VIRGO', size=32652.0),
        DatabaseEntry(
            source='SOHO', provider='SDAC', physobs='intensity',
            fileid='/archive/soho/private/data/processed/virgo/loi/VIRGO-LOI-ALL-PIXELS-LEVEL2-19960401-20210430_V01.fits',
            observation_time_start=datetime(1996, 4, 1, 0, 0),
            observation_time_end=datetime(2021, 4, 30, 23, 59),
            instrument='VIRGO', size=1677722.0),
        DatabaseEntry(
            source='SOHO', provider='SDAC', physobs='intensity',
            fileid='/archive/soho/private/data/processed/virgo/sph/VIRGO_D4.2_SPH_960411_120914.tar.gz',
            observation_time_start=datetime(1996, 4, 11, 0, 0),
            observation_time_end=datetime(2012, 9, 14, 0, 0),
            instrument='VIRGO', size=512000.0),
        DatabaseEntry(
            source='SOHO', provider='SDAC', physobs='intensity',
            fileid='/archive/soho/private/data/processed/virgo/level1/1212/HK/121222_1.H01',
            observation_time_start=datetime(2012, 12, 23, 23, 59, 3),
            observation_time_end=datetime(2012, 12, 24, 23, 59, 2),
            instrument='VIRGO', size=155.0),
        DatabaseEntry(
            source='SOHO', provider='SDAC', physobs='intensity',
            fileid='/archive/soho/private/data/processed/virgo/level1/1212/LOI/121224_1.L01',
            observation_time_start=datetime(2012, 12, 23, 23, 59, 3),
            observation_time_end=datetime(2012, 12, 24, 23, 59, 2),
            instrument='VIRGO', size=329.0),
        DatabaseEntry(
            source='SOHO', provider='SDAC', physobs='intensity',
            fileid='/archive/soho/private/data/processed/virgo/level1/1212/SPM/121222_1.S02',
            observation_time_start=datetime(2012, 12, 23, 23, 59, 3),
            observation_time_end=datetime(2012, 12, 24, 23, 59, 2),
            instrument='VIRGO', size=87.0),
        DatabaseEntry(
            source='SOHO', provider='SDAC', physobs='intensity',
            fileid='/archive/soho/private/data/processed/virgo/level1/1212/DIARAD/121222_1.D01',
            observation_time_start=datetime(2012, 12, 24, 0, 1, 58),
            observation_time_end=datetime(2012, 12, 25, 0, 1, 57),
            instrument='VIRGO', size=14.0),
        DatabaseEntry(
            source='SOHO', provider='SDAC', physobs='intensity',
            fileid='/archive/soho/private/data/processed/virgo/tsi_full/VIRGO_TSI_Minute.fits',
            observation_time_start=datetime(1996, 2, 22, 0, 0, 50),
            observation_time_end=datetime(2023, 2, 20, 23, 57, 13),
            instrument='VIRGO', size=332814.0),
    ]

    for e in entries:
        assert e in expected
    for e in expected:
        assert e in entries


def test_create_display_table_missing_entries():
    with pytest.raises(TypeError):
        _create_display_table([], ['some', 'columns'])


def test_create_display_table_empty_db():
    with pytest.raises(TypeError):
        _create_display_table(Database('sqlite:///'), ['id'])


def test_create_display_table_missing_columns():
    with pytest.raises(TypeError):
        _create_display_table([DatabaseEntry()], [])


def test_create_display_table():
    conf.max_width = 500
    entries = [
        DatabaseEntry(
            id=1, source='SOHO', provider='SDAC', physobs='intensity',
            fileid='/archive/soho/...',
            observation_time_start=datetime(2001, 1, 1, 7, 0, 14),
            observation_time_end=datetime(2001, 1, 1, 7, 0, 21),
            instrument='EIT', size=259.0, wavemin=171.0,
            wavemax=171.0, tags=[Tag('foo'), Tag('bar')]),
        DatabaseEntry(
            id=2, source='GONG', provider='NSO', physobs='LOS_velocity',
            fileid='pptid=11010...',
            observation_time_start=datetime(2010, 1, 1, 0, 59),
            observation_time_end=datetime(2010, 1, 1, 1),
            download_time=datetime(2014, 6, 15, 3, 42, 55, 123456),
            instrument='Merged gong', size=944.0,
            wavemin=6768.0, wavemax=6768.0, starred=True)]
    columns = [
        'id', 'source', 'provider', 'physobs', 'fileid', 'download_time',
        'observation_time_start', 'instrument', 'size',
        'wavemin', 'path', 'starred', 'tags']
    table = _create_display_table(entries, columns)
    filedir = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(filedir, 'test_table.txt'), 'r') as f:
        stored_table = f.read()
    assert table.__str__().strip() == stored_table.strip()
    conf.reset('max_width')
