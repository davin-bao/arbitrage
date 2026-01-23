from setuptools import setup, find_packages

setup(
    name="arbitrage",
    version="0.1.0",
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'ccxt==4.5.32',
        'PyYAML==6.0.3',
        'requests==2.32.5',
        'aiohttp==3.13.3',
        'python-dotenv>=1.0.0',
    ],
    python_requires='>=3.8',
)