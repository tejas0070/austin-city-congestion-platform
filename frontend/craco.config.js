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

      // Route all mapbox-gl imports (including kepler.gl internals) through
      // maplibre-gl — avoids Mapbox token requirements entirely.
      webpackConfig.resolve.alias = {
        ...webpackConfig.resolve.alias,
        'mapbox-gl': 'maplibre-gl',
      };

      // kepler.gl ships .cjs files; webpack 5 asset modules treat unknown
      // extensions as static files and return a URL string instead of the
      // module exports. The rule must live INSIDE CRA's oneOf block before the
      // catch-all asset rule — pushing to the outer rules array runs too late.
      const oneOfRule = webpackConfig.module.rules.find(
        (r) => Array.isArray(r.oneOf)
      );
      if (!oneOfRule) {
        throw new Error(
          'CRA webpack config no longer has a oneOf rule — update craco.config.js'
        );
      }
      oneOfRule.oneOf.unshift({ test: /\.cjs$/, type: 'javascript/auto' });

      // Prevent "fullySpecified" errors from ESM packages that omit extensions
      webpackConfig.module.rules.push({
        test: /\.m?js$/,
        resolve: { fullySpecified: false },
      });

      return webpackConfig;
    },
  },
};
