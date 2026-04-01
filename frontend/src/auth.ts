const POOL_ID = import.meta.env.VITE_COGNITO_USER_POOL_ID || ''
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID || ''

export const authEnabled = !!(POOL_ID && CLIENT_ID)

let _pool: any = null

async function getPool() {
  if (_pool) return _pool
  const { CognitoUserPool } = await import('amazon-cognito-identity-js')
  _pool = new CognitoUserPool({ UserPoolId: POOL_ID, ClientId: CLIENT_ID })
  return _pool
}

export async function getCurrentSession(): Promise<any> {
  if (!authEnabled) return null
  const pool = await getPool()
  const user = pool.getCurrentUser()
  if (!user) return null
  return new Promise((resolve) => {
    user.getSession((err: any, session: any) => resolve(err ? null : session))
  })
}

export async function getIdToken(): Promise<string | null> {
  const s = await getCurrentSession()
  return s?.getIdToken().getJwtToken() || null
}

export async function login(email: string, password: string): Promise<{ success: boolean; newPasswordRequired?: boolean; userObj?: any }> {
  if (!authEnabled) return { success: true }
  const { CognitoUser, AuthenticationDetails } = await import('amazon-cognito-identity-js')
  const pool = await getPool()
  const user = new CognitoUser({ Username: email, Pool: pool })
  const authDetails = new AuthenticationDetails({ Username: email, Password: password })
  return new Promise((resolve, reject) => {
    user.authenticateUser(authDetails, {
      onSuccess: () => resolve({ success: true }),
      onFailure: (err: any) => reject(err),
      newPasswordRequired: () => resolve({ success: false, newPasswordRequired: true, userObj: user }),
    })
  })
}

export async function completeNewPassword(user: any, newPassword: string): Promise<void> {
  return new Promise((resolve, reject) => {
    user.completeNewPasswordChallenge(newPassword, {}, {
      onSuccess: () => resolve(),
      onFailure: (err: any) => reject(err),
    })
  })
}

export function logout() {
  if (!authEnabled || !_pool) return
  _pool.getCurrentUser()?.signOut()
}
