module.exports = {
  webpack: {
    configure: (webpackConfig) => {
      webpackConfig.resolve.fallback = {
        ...webpackConfig.resolve.fallback,
        stream: require.resolve('stream-browserify'),
        buffer: require.resolve('buffer/'),
        crypto: require.resolve('crypto-browserify'),
        path: require.resolve('path-browserify'),
        assert: require.resolve('assert/'),
        url: require.resolve('url/'),
        util: require.resolve('util/'),
        os: require.resolve('os-browserify/browser'),
        fs: false,
        net: false,
        tls: false,
      };
      return webpackConfig;
    },
  },
};
