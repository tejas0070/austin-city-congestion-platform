import { createStore, combineReducers, applyMiddleware, compose } from 'redux';
import keplerGlReducer from '@kepler.gl/reducers';
import { enhanceReduxMiddleware } from '@kepler.gl/reducers';

// Start kepler read-only so its default "add data / upload" empty-state chrome
// never appears during the cold-start window before our datasets load. The app
// drives everything through its own Sidebar; kepler's editor panel is unused.
const customKeplerReducer = keplerGlReducer.initialState({
  uiState: {
    readOnly: true,
    currentModal: null,
  },
});

const reducers = combineReducers({
  keplerGl: customKeplerReducer,
});

const middlewares = enhanceReduxMiddleware([]);

const composeEnhancers =
  (typeof window !== 'undefined' && window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__) || compose;

const store = createStore(
  reducers,
  {},
  composeEnhancers(applyMiddleware(...middlewares))
);

export default store;
