import { JOINTS } from '@/lib/lists'

// The shoulder blade moves with the shoulder, and the forearm turns at the elbow, so a lateral
// raise or a curl still counts as one joint.
const COUNTS_AS: Record<string, string> = { 'Shoulder Blade': 'Shoulder', Forearm: 'Elbow' }

/** Whether joint movements ("hip extension", "knee extension") make a compound exercise: two or
 *  more joints is compound, one is isolation, none is not known. */
export function isCompound(jointMovements: string[]): boolean | null {
  const joints = new Set(jointMovements.map((v) => {
    const [joint] = JOINTS.find(([j, moves]) => moves.some((m) => v === `${j.toLowerCase()} ${m}`))!
    return COUNTS_AS[joint] ?? joint
  }))
  return joints.size === 0 ? null : joints.size > 1
}
